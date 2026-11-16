"""Generate R6 distortion swaps as verbatim source spans with the frozen swap labeller.

The labeller (`anthropic/claude-haiku-5.5`, swap prompt `swap-v1` in the
labeller-v2 family) is given the question, the gold, the critical facts, the
board unit that contradicts the source, and that agent's source context. It
must return one span copied verbatim from the context.

Every generated span is checked before use:
- the span is an exact substring of the source context;
- `distortion_gate`: swap recall >= 0.8 and replaced-unit recall >= 0.5;
- `delivery_reasons`: not question text, not a document header, not a refusal,
  not a data-list fragment, and fact recall >= 0.8.

No accepted span is used by any run here; this script only produces the swap
records and the check results. Every call is logged (intent before dispatch,
result after). No paper, plan or cohort file is read or changed.

    ./run.sh python -m scripts.generate_distortion_swaps --cases e4-25
    ./run.sh python -m scripts.generate_distortion_swaps --run --cap-usd 0.50
    ./run.sh python -m scripts.generate_distortion_swaps --report
"""
import argparse
import hashlib
import json
import math
from pathlib import Path

from src.audit.e4_fix_gates import delivery_reasons, distortion_gate, recall
from src.audit.pilot_common import digest

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'rebuttal/pilots/20261112_swap_labeller'
PROMPT = OUT / 'swap_prompt_v1.json'
PROMPT_MANIFEST = OUT / 'swap_prompt_v1.manifest.json'
CASES = OUT / 'swap_cases.jsonl'
CALLS = OUT / 'calls.jsonl'
SWAPS = OUT / 'swaps.jsonl'
REPORT = OUT / 'swap_report.md'
P23 = ROOT / 'rebuttal/pilots/20261111_e4_phase23/actions_phase23.json'
STAGE2_MATCHER = ROOT / 'rebuttal/results/batch1/expansion_stage2/matcher'
STAGE2 = ROOT / 'rebuttal/pilots/20261112_expansion_stage2'
MODEL = 'anthropic/claude-haiku-5.5'
PRICE_IN = 0.10 / 1_000_000
PRICE_OUT = 0.50 / 1_000_000
MAX_TOKENS = 500
CAP = 0.50

SYSTEM_KEYS = ('version', 'system', 'system_sha256')


def load_prompt():
    raw = PROMPT.read_bytes()
    spec = json.loads(raw)
    man = json.loads(PROMPT_MANIFEST.read_text())
    syshash = hashlib.sha256(spec['system'].encode()).hexdigest()
    assert syshash == spec['system_sha256'] == man['system_sha256']
    assert hashlib.sha256(raw).hexdigest() == man['file_sha256']
    assert spec['version'] == man['version'] == 'swap-v1'
    assert man['model'] == MODEL
    return spec


# ---------------------------------------------------------------- case building
def board_facts(carriers, unit_id):
    """Fact ids a board unit carries and is not faithful to."""
    out = {}
    for c in carriers:
        for u in c.get('board') or []:
            if unit_id in (u.get('unit_ids') or []) and u.get('fidelity') != 'faithful':
                out[c['fact_id']] = u.get('fidelity')
    return out


def base_case(source, instance, model, question, gold, facts, carriers, board, contexts,
              unit_id):
    dist = board_facts(carriers, unit_id)
    unit = next((u for u in board if u['unit_id'] == unit_id), None)
    agent = unit['agent_id'] if unit else None
    ctx = '\n'.join(s['text'] for s in contexts if s['agent_id'] == agent)
    assert dist and unit is not None and ctx, (instance, model, unit_id)
    return {
        'key': digest([source, instance, model, str(agent), unit_id]),
        'source': source, 'instance_id': instance, 'model': model,
        'question': question, 'gold': gold,
        'target_agent': agent, 'target_unit_id': unit_id,
        'replaced_text': unit['text'],
        'distorted_facts': {fid: facts[fid] for fid in sorted(dist)},
        'fact_fidelity': dist,
        'context': ctx,
    }


def cases_e4():
    rows = json.loads(P23.read_text())
    out = []
    for r in rows:
        if r.get('group') != 'distortion':
            continue
        uid = r['target_swap']['unit_id']
        out.append(base_case('e4-25', r['instance_id'], r['model'], r['question'],
                             r['gold_answer'], {f['fact_id']: f['text'] for f in r['facts']['facts']},
                             r['carriers']['facts'], r['board_units'], r['source_contexts'], uid))
    assert len(out) == 25, len(out)
    return out


def cases_stage2():
    from scripts.run_expansion_stage2 import MODELS, packages
    out, seen = [], set()
    recs = [json.loads(p.read_text()) for p in STAGE2_MATCHER.glob('*.json')]
    pk = {m: packages(m) for m in MODELS}
    for rec in recs:
        if rec.get('status') != 'ok' or rec.get('diagnosis') != 'distortion':
            continue
        model, inst = rec['model'], rec['instance_id']
        p = pk[model][inst]
        facts = {f['fact_id']: f['text'] for f in rec['facts']['facts']}
        carriers = rec['carriers']['facts']
        board = p['checkpoints']['board']
        # target unit: the distorted board unit carrying the most facts
        cover = {}
        for c in carriers:
            for u in c.get('board') or []:
                if u.get('fidelity') != 'faithful':
                    for uid in u.get('unit_ids') or []:
                        cover.setdefault(uid, set()).add(c['fact_id'])
        if not cover:
            continue
        uid = sorted(cover, key=lambda u: (-len(cover[u]), u))[0]
        c = base_case('stage2', inst, model, p['question'], p['gold_answer'], facts,
                      carriers, board, p['source_contexts'], uid)
        if c['key'] in seen:
            continue
        seen.add(c['key'])
        out.append(c)
    return out


def build_cases(source):
    rows = {'e4-25': cases_e4, 'stage2': cases_stage2}[source]()
    OUT.mkdir(parents=True, exist_ok=True)
    with CASES.open('w') as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + '\n')
    chars = [len(render(r)) for r in rows]
    print(json.dumps({'source': source, 'cases': len(rows),
                      'unique_instances': len({r['instance_id'] for r in rows}),
                      'mean_chars': round(sum(chars) / len(chars)),
                      'est_usd': round(sum(math.ceil(c / 4) for c in chars) * PRICE_IN, 4),
                      'cases_sha256': digest(CASES.read_bytes())}, indent=1))


# ------------------------------------------------------------------ model calls
def render(row):
    lines = ['QUESTION', row['question'], '', 'GOLD ANSWER', str(row['gold']), '',
             'CRITICAL FACTS TO RESTORE']
    for fid, text in row['distorted_facts'].items():
        lines.append(f'[{fid}] {text}')
    lines += ['', 'BOARD UNIT TO REPLACE (it contradicts the source)', row['replaced_text'],
              '', f"SOURCE CONTEXT (agent {row['target_agent']})", row['context'], '',
              'Select one verbatim span from SOURCE CONTEXT that states one of the critical '
              'facts and supports the gold answer. Return strict JSON only.']
    return '\n'.join(lines)


def parse_span(text):
    """Last complete JSON object that has a `span` key (v2-family rule)."""
    objs, depth, start = [], 0, None
    for i, ch in enumerate(text or ''):
        if ch == '{':
            if depth == 0:
                start = i
            depth += 1
        elif ch == '}' and depth:
            depth -= 1
            if depth == 0 and start is not None:
                try:
                    d = json.loads(text[start:i + 1])
                except Exception:
                    d = None
                if isinstance(d, dict) and 'span' in d:
                    objs.append(d)
    return objs[-1] if objs else None


def check(row, parsed):
    span = (parsed or {}).get('span')
    if not span or not str(span).strip():
        return {'accepted': False, 'reasons': ['labeller returned no span']}
    span = str(span)
    reasons = []
    if span not in row['context']:
        reasons.append('span is not a verbatim substring of the source context')
    fid = parsed.get('fact_id')
    dist = row['distorted_facts']
    if fid not in dist:
        fid = max(dist, key=lambda k: recall(span, dist[k]))
    dg = distortion_gate(span, dist, row['replaced_text'])
    dr = delivery_reasons(span, dist[fid], row['question'])
    if not dg['ok']:
        reasons.append(dg['reason'])
    reasons.extend(dr)
    return {'accepted': not reasons, 'reasons': reasons, 'fact_id': fid,
            'gate': dg, 'delivery_reasons': dr,
            'verbatim': span in row['context'],
            'source_agent': parsed.get('source_agent')}


def one(row, spec):
    from utility.apis.openrouter_api import single_request
    from utility.apis.base import APIRequest
    user = render(row)
    meta = {'case': row['key'], 'prompt_version': spec['version'],
            'family': spec['family'], 'system_sha256': spec['system_sha256'],
            'file_sha256': json.loads(PROMPT_MANIFEST.read_text())['file_sha256'],
            'openrouter_reasoning': False}
    req = APIRequest(system_query=spec['system'], user_query=user, model=MODEL,
                     max_tokens=MAX_TOKENS, temperature=0, metadata=meta)
    resp = single_request(req)
    usage = resp.usage or {}
    est_in = math.ceil(len(user) / 4) + math.ceil(len(spec['system']) / 4)
    cost = (usage.get('prompt_tokens', est_in) * PRICE_IN
            + usage.get('completion_tokens', 0) * PRICE_OUT)
    parsed = parse_span(resp.content or '')
    check_res = check(row, parsed)
    return {'event': 'result', 'case': row['key'], 'instance_id': row['instance_id'],
            'model': row['model'], 'target_agent': row['target_agent'],
            'target_unit_id': row['target_unit_id'],
            'question': row['question'], 'gold': row['gold'],
            'replaced_text': row['replaced_text'],
            'distorted_facts': row['distorted_facts'],
            'prompt_version': spec['version'], 'family': spec['family'],
            'system_sha256': spec['system_sha256'],
            'file_sha256': meta['file_sha256'],
            'success': resp.success, 'error': resp.error, 'raw': resp.content,
            'parsed': parsed, 'span': (parsed or {}).get('span'),
            'usage': usage, 'cost_usd': round(cost, 8), **check_res}


def run(cap):
    spec = load_prompt()
    rows = [json.loads(l) for l in CASES.read_text().splitlines() if l.strip()]
    latest = {}
    spent = 0.0
    if CALLS.exists():
        for line in CALLS.read_text().splitlines():
            if line.strip():
                rec = json.loads(line)
                if rec.get('event') == 'result':
                    latest[rec['case']] = rec
                    spent += rec.get('cost_usd') or 0
    todo = [r for r in rows if r['key'] not in latest]
    print(json.dumps({'cases': len(rows), 'already_logged': len(latest),
                      'todo': len(todo), 'spent_usd': round(spent, 6),
                      'cap_usd': cap}), flush=True)
    with CALLS.open('a') as log, SWAPS.open('a') as swaps:
        for row in todo:
            reserve = ((math.ceil(len(render(row)) / 4)
                        + math.ceil(len(spec['system']) / 4)) * PRICE_IN * 1.5
                       + MAX_TOKENS * PRICE_OUT)
            if spent + reserve > cap:
                print(json.dumps({'stopped': 'cap', 'spent': round(spent, 6),
                                  'remaining': len(todo)}), flush=True)
                break
            intent = {'event': 'intent', 'case': row['key'],
                      'instance_id': row['instance_id'], 'model': row['model'],
                      'prompt_version': spec['version'],
                      'system_sha256': spec['system_sha256']}
            log.write(json.dumps(intent, ensure_ascii=False) + '\n')
            log.flush()
            try:
                rec = one(row, spec)
            except Exception as exc:
                rec = {'event': 'result', 'case': row['key'],
                       'instance_id': row['instance_id'], 'model': row['model'],
                       'prompt_version': spec['version'],
                       'system_sha256': spec['system_sha256'],
                       'success': False, 'error': type(exc).__name__ + ': ' + str(exc),
                       'raw': None, 'parsed': None, 'span': None,
                       'cost_usd': 0.0, 'accepted': False,
                       'reasons': ['transport failure']}
            spent += rec.get('cost_usd') or 0
            log.write(json.dumps(rec, ensure_ascii=False) + '\n')
            log.flush()
            swaps.write(json.dumps({k: rec.get(k) for k in (
                'case', 'instance_id', 'model', 'target_agent', 'target_unit_id',
                'question', 'gold', 'replaced_text', 'distorted_facts', 'span',
                'parsed', 'accepted', 'reasons', 'fact_id', 'gate',
                'delivery_reasons', 'verbatim', 'source_agent', 'cost_usd')},
                ensure_ascii=False) + '\n')
            swaps.flush()
            print(json.dumps({'case': row['instance_id'] + '/' + str(row['model']),
                              'accepted': rec['accepted'],
                              'usd': round(spent, 5)}), flush=True)
    print(json.dumps({'spent_usd': round(spent, 6), 'cap_usd': cap}), flush=True)


def report():
    spec = load_prompt()
    rows = [json.loads(l) for l in CASES.read_text().splitlines() if l.strip()]
    calls = [json.loads(l) for l in CALLS.read_text().splitlines() if l.strip()]
    results = {}
    for c in calls:
        if c.get('event') == 'result':
            results[c['case']] = c
    accepted = [r for r in rows if (results.get(r['key']) or {}).get('accepted')]
    rejected = [r for r in rows if not (results.get(r['key']) or {}).get('accepted')]
    spent = sum((c.get('cost_usd') or 0) for c in calls if c.get('event') == 'result')
    reason_counts = {}
    for r in rejected:
        for reason in (results.get(r['key']) or {}).get('reasons') or ['missing result']:
            reason_counts[reason] = reason_counts.get(reason, 0) + 1
    lines = ['# Distortion swap generation, swap-v1\n',
             f'Prompt `{spec["version"]}` ({spec["family"]}), file sha256 '
             f'`{json.loads(PROMPT_MANIFEST.read_text())["file_sha256"]}`, system sha256 '
             f'`{spec["system_sha256"]}`, model `{MODEL}`, temperature 0. '
             f'Cases {len(rows)}; calls {sum(1 for c in calls if c.get("event") == "result")}; '
             f'spend ${spent:.6f} against a ${CAP:.2f} cap.\n',
             f'Call log: `{CALLS.relative_to(ROOT)}`; case list: `{CASES.relative_to(ROOT)}` '
             f'({digest(CASES.read_bytes())}); swap records: `{SWAPS.relative_to(ROOT)}`.\n',
             '## Gate results\n',
             f'- Accepted: **{len(accepted)}** of {len(rows)}.',
             f'- Rejected: **{len(rejected)}**.',
             '- Gate: span verbatim in the source context; `distortion_gate` swap recall '
             '>= 0.8 and replaced-unit recall >= 0.5; `delivery_reasons` clear (not question, '
             'header, refusal or data list; recall >= 0.8).\n',
             '| reason | cases |', '| --- | ---: |']
    for reason, n in sorted(reason_counts.items(), key=lambda kv: -kv[1]):
        lines.append(f'| {reason} | {n} |')
    lines += ['', '## Accepted swaps\n']
    if not accepted:
        lines.append('None. No swap from this source passes the gate.\n')
    for r in accepted:
        c = results[r['key']]
        lines += [f"### {r['instance_id']} / {r['model']} / {r['target_unit_id']}\n",
                  f"Question: {r['question']}  ",
                  f"Gold: `{r['gold']}`  ",
                  f"Span: `{c['span']}`  ",
                  f"Fact: {c['fact_id']} — `{r['distorted_facts'].get(c['fact_id'], '')}`  ",
                  f"Swap recall: {c['gate']['swap_recall']}; replaced recall: "
                  f"{c['gate']['replaced_recall']}.\n"]
    lines += ['## Rejected swaps\n',
              'The rejected spans and their reasons are in `swaps.jsonl`.\n']
    REPORT.write_text('\n'.join(lines) + '\n')
    print(json.dumps({'cases': len(rows), 'accepted': len(accepted), 'rejected': len(rejected),
                      'reasons': reason_counts, 'spent_usd': round(spent, 6),
                      'report': str(REPORT.relative_to(ROOT))}, indent=1))


def set_out(subdir):
    """Point case/call/swap/report outputs at a subdirectory; the frozen
    prompt and its manifest stay in the base directory."""
    global OUT, CASES, CALLS, SWAPS, REPORT
    OUT = OUT / subdir
    OUT.mkdir(parents=True, exist_ok=True)
    CASES = OUT / 'swap_cases.jsonl'
    CALLS = OUT / 'calls.jsonl'
    SWAPS = OUT / 'swaps.jsonl'
    REPORT = OUT / 'swap_report.md'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--cases', choices=['e4-25', 'stage2'])
    ap.add_argument('--out', default=None, help='subdirectory under the pilot dir for outputs')
    ap.add_argument('--run', action='store_true')
    ap.add_argument('--report', action='store_true')
    ap.add_argument('--cap-usd', type=float, default=CAP)
    a = ap.parse_args()
    if a.out:
        set_out(a.out)
    if a.cases:
        build_cases(a.cases)
    if a.run:
        run(a.cap_usd)
    if a.report:
        report()


if __name__ == '__main__':
    main()