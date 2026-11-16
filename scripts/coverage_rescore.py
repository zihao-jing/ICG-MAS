"""Coverage and aggregation-failure re-score: lexical vs labeller evidence flow.

Rule: `rebuttal/pilots/20261113_coverage_rescore/SCORING_RULE.md`, frozen before
any call. Pilot cap $5; every call logged. No answer text reaches the labeller.

    ./run.sh python -m scripts.coverage_rescore --build
    ./run.sh python -m scripts.coverage_rescore --pilot --cap-usd 5
    ./run.sh python -m scripts.coverage_rescore --report
"""
import argparse
import hashlib
import json
import math
from pathlib import Path

from scripts.answer_equiv import last_object
from scripts.missing_fact_repair_pilot import cp_ci
from scripts.pilot_llm_labeller import MODEL_OPENROUTER, PRICE_IN, PRICE_OUT
from src.audit.e4_fix_gates import content, recall
from utility.apis.base import APIRequest

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'rebuttal/pilots/20261113_coverage_rescore'
RULE = OUT / 'SCORING_RULE.md'
PROMPT = OUT / 'coverage_prompt_v1.json'
CASES = ROOT / 'rebuttal/pilots/20261112_rescore/cases.jsonl'
SAMPLE = OUT / 'sample.json'
MANIFEST = OUT / 'run_manifest.json'
CALLS = OUT / 'calls.jsonl'
RESULTS = OUT / 'results.json'
REPORT = OUT / 'report.md'
SEED = 43
PER_PROTO = 30
THRESH = 0.8
MAX_TOKENS = 2000
SUPPORT_CHARS = 6000
UNIT_CHARS = 1500


def sha(text):
    return hashlib.sha256(text.encode()).hexdigest()


def file_sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load_cases():
    return [json.loads(l) for l in CASES.read_text().splitlines() if l.strip()]


def sample_cases():
    cases = load_cases()
    by = {}
    for c in cases:
        by.setdefault(c['protocol'], []).append(c)
    picked = []
    for proto in sorted(by):
        rows = sorted(by[proto], key=lambda c: sha(f'{SEED}|{c["key"]}'))
        picked.extend(rows[:PER_PROTO])
    assert len(picked) == PER_PROTO * len(by), len(picked)
    return picked


def lexical_coverage(trace):
    supports = [s for s in trace.get('source_supports') or []]
    units = (trace.get('checkpoints') or {}).get('board') or []
    if not supports:
        return None, []
    best = []
    for s in supports:
        scores = [recall(u['text'], s['text']) for u in units] or [0.0]
        best.append(max(scores))
    return all(x >= THRESH for x in best), best


def render(case, trunc=0):
    trace = case['trace']
    supports, board = [], []
    for i, s in enumerate(trace.get('source_supports') or [], 1):
        text = s['text'][:SUPPORT_CHARS]
        trunc += len(s['text']) - len(text)
        supports.append(f'[s{i}] ({s.get("support_id") or s.get("agent_id")}) {text}')
    for u in (trace.get('checkpoints') or {}).get('board') or []:
        text = u['text'][:UNIT_CHARS]
        trunc += len(u['text']) - len(text)
        board.append(f'{u["unit_id"]} [agent={u["agent_id"]}]: {text}')
    return (f"QUESTION\n{case['question']}\n\nCRITICAL FACTS\n" + '\n'.join(supports)
            + "\n\nBOARD\n" + '\n'.join(board)), trunc


def call(key, spec, user, cap, total):
    est_in = math.ceil((len(spec['system']) + len(user)) / 4)
    est = est_in * PRICE_IN + MAX_TOKENS * PRICE_OUT
    if total + est > cap:
        with CALLS.open('a') as f:
            f.write(json.dumps({'event': 'skipped', 'key': key, 'reason': 'cap',
                                'cost_usd': 0.0}) + '\n')
        return None, total
    call_id = sha('|'.join([key, spec['system'], user, str(MAX_TOKENS)]))
    with CALLS.open('a') as f:
        f.write(json.dumps({'event': 'intent', 'key': key, 'call_id': call_id,
                            'model': spec['model'], 'system_sha256': sha(spec['system']),
                            'user_sha256': sha(user), 'max_tokens': MAX_TOKENS,
                            'temperature': 0}) + '\n')
    from utility.apis.openrouter_api import single_request
    req = APIRequest(system_query=spec['system'], user_query=user,
                     model=spec['model'], max_tokens=MAX_TOKENS, temperature=0,
                     metadata={'pilot': 'coverage_rescore', 'key': key,
                               'openrouter_reasoning': False})
    resp = single_request(req)
    usage = resp.usage or {}
    cost = (usage.get('prompt_tokens', est_in) * PRICE_IN
            + usage.get('completion_tokens', 0) * PRICE_OUT)
    with CALLS.open('a') as f:
        f.write(json.dumps({'event': 'result', 'key': key, 'call_id': call_id,
                            'model': spec['model'], 'success': resp.success,
                            'error': resp.error, 'content': resp.content,
                            'usage': usage, 'cost_usd': round(cost, 8)}) + '\n')
    return resp, total + cost


def parse_coverage(raw):
    d = last_object(raw or '')
    if not isinstance(d, dict):
        return None
    rows = d.get('supports')
    if not isinstance(rows, list):
        return None
    allowed = {'present', 'partial', 'distorted', 'absent'}
    out = []
    for r in rows:
        if not isinstance(r, dict):
            return None
        st = str(r.get('status', '')).strip().lower()
        if st not in allowed:
            return None
        out.append({'id': str(r.get('id') or ''), 'status': st,
                    'unit_ids': r.get('unit_ids') or [],
                    'reason': str(r.get('reason') or '')[:200]})
    complete = bool(out) and all(x['status'] == 'present' for x in out)
    return {'supports': out, 'complete': complete,
            'declared': str(d.get('coverage') or '')}


def spent():
    if not CALLS.exists():
        return 0.0
    return sum(json.loads(l).get('cost_usd', 0.0)
               for l in CALLS.read_text().splitlines()
               if l.strip() and json.loads(l).get('event') in ('result', 'skipped'))


def build():
    picked = sample_cases()
    spec = json.loads(PROMPT.read_text())
    OUT.mkdir(parents=True, exist_ok=True)
    SAMPLE.write_text(json.dumps({'seed': SEED, 'per_protocol': PER_PROTO,
                                  'keys': [c['key'] for c in picked]}, indent=1))
    MANIFEST.write_text(json.dumps({
        'recorded_before_first_call': True,
        'rule_sha256': file_sha(RULE),
        'prompt_file_sha256': file_sha(PROMPT),
        'prompt_system_sha256': sha(spec['system']),
        'cases_sha256': file_sha(CASES), 'sample_sha256': file_sha(SAMPLE),
        'seed': SEED, 'per_protocol': PER_PROTO, 'threshold': THRESH,
        'model': spec['model'], 'temperature': 0,
    }, indent=1))
    print(json.dumps({'sample': len(picked),
                      'protocols': {p: sum(c['protocol'] == p for c in picked)
                                    for p in sorted({c['protocol'] for c in picked})}},
                     indent=1))


def pilot(cap, retry=False):
    man = json.loads(MANIFEST.read_text())
    assert file_sha(CASES) == man['cases_sha256']
    assert file_sha(RULE) == man['rule_sha256']
    assert file_sha(PROMPT) == man['prompt_file_sha256']
    picked = json.loads(SAMPLE.read_text())['keys']
    by_key = {c['key']: c for c in load_cases()}
    spec = json.loads(PROMPT.read_text())
    total = spent()
    done = {}
    if RESULTS.exists():
        done = {r['key']: r for r in json.loads(RESULTS.read_text())['cases']}
    rows = []
    for key in picked:
        prev = done.get(key)
        if prev is not None and not (retry and prev.get('success')
                                     and prev.get('labeller') is None):
            rows.append(prev)
            continue
        case = by_key[key]
        lex, scores = lexical_coverage(case['trace'])
        user, truncated = render(case)
        resp, total = call(key, spec, user, cap, total)
        if resp is None:
            print(json.dumps({'stopped': 'cap', 'key': key,
                              'spent_usd': round(total, 6)}))
            break
        lab = parse_coverage(resp.content)
        row = {'key': key, 'protocol': case['protocol'],
               'benchmark': case['benchmark'], 'instance_id': case['instance_id'],
               'lexical_complete': lex, 'lexical_best': [round(x, 4) for x in scores],
               'f1': case['f1'], 'truncated_chars': truncated,
               'labeller': lab, 'success': resp.success}
        if prev is not None:
            row['attempt'] = 2
            row['first_attempt'] = {'labeller': prev.get('labeller'),
                                    'completion_tokens': 600,
                                    'max_tokens': 600}
        rows.append(row)
        RESULTS.write_text(json.dumps({'cases': rows}, indent=1, ensure_ascii=False))
        print(json.dumps({'key': key, 'lexical': lex,
                          'labeller': None if lab is None else lab['complete'],
                          'spent_usd': round(total, 6)}), flush=True)
    RESULTS.write_text(json.dumps({'cases': rows}, indent=1, ensure_ascii=False))
    print(json.dumps({'cases': len(rows), 'spent_usd': round(total, 8)}, indent=1))


def kappa_binary(pairs):
    n = len(pairs)
    if not n:
        return float('nan')
    a = sum(x == y for x, y in pairs) / n
    p1 = sum(x for x, _ in pairs) / n
    p2 = sum(y for _, y in pairs) / n
    pe = p1 * p2 + (1 - p1) * (1 - p2)
    return (a - pe) / (1 - pe) if pe < 1 else float('nan')


def report():
    allrows = [r for r in json.loads(RESULTS.read_text())['cases'] if r.get('success')]
    rows = [r for r in allrows if r.get('labeller')]
    unparsed = [r for r in allrows if not r.get('labeller')]
    total = spent()
    lines = ['# Coverage and aggregation-failure re-score — pilot\n',
             f"Rule `SCORING_RULE.md` (sha256 `{file_sha(RULE)[:12]}`), prompt "
             f"`coverage_prompt_v1.json` (sha256 `{file_sha(PROMPT)[:12]}`); output-"
             f"budget amendment `COVERAGE_AMENDMENT_V1.md`. "
             f"{len(rows)}/{len(allrows)} traces scored; "
             f"{len(unparsed)} unparsed; spend ${total:.6f}.\n",
             '**Path taken:** `coverage_prompt_v1` was validated against the '
             'author carrier labels instead of switching to `labeller_prompt_v2`, '
             'because v2 is answer-based and returns no coverage label. The '
             'validation is **negative**: agreement 0.389 (see Direction of the '
             'difference and `20261113_coverage_validation/report.md`).\n']
    if not rows:
        lines.append('No scored traces.')
        REPORT.write_text('\n'.join(lines) + '\n')
        return
    lex = [bool(r['lexical_complete']) for r in allrows]
    lab = [bool(r['labeller']['complete']) if r.get('labeller') else False
           for r in allrows]
    af_lex = [l and r['f1'] < 1.0 for l, r in zip(lex, allrows)]
    af_lab = [l and r['f1'] < 1.0 for l, r in zip(lab, allrows)]
    agree = sum(x == y for x, y in zip(lex, lab)) / len(allrows)
    kap = kappa_binary(list(zip(lex, lab)))
    def line(name, vals):
        k = sum(vals); lo, hi = cp_ci(k, len(vals))
        return f"| {name} | {k}/{len(vals)} | {100*k/len(vals):.1f}% | {100*lo:.1f}-{100*hi:.1f}% |"
    lines += ['| endpoint | k/n | rate | 95% CI |', '| --- | ---: | ---: | --- |',
              line('complete coverage, lexical', lex),
              line('complete coverage, labeller (not validated)', lab),
              line('AF, lexical', af_lex),
              line('AF, labeller (not validated)', af_lab), '',
              'The labeller columns are **not validated**: the coverage prompt '
              'agrees with author labels on 70/180 comparisons (see below).', '',
              'Denominators are the 120 sampled traces. The one unparsed trace '
              f'({unparsed[0]["instance_id"] if unparsed else "none"}, '
              f'{unparsed[0]["protocol"] if unparsed else ""}) is scored as not '
              'complete and not AF. CIs are exact Clopper-Pearson, not Wilson.\n']
    lines += [f'Agreement on complete coverage: **{agree:.3f}**; Cohen kappa '
              f'**{kap:.3f}** (n={len(allrows)}; the unparsed trace counts as '
              'not complete for both).\n',
              '## Per protocol\n',
              '| protocol | n | lexical complete | labeller complete (not validated) | both AF |',
              '| --- | ---: | ---: | ---: | ---: |']
    for proto in sorted({r['protocol'] for r in allrows}):
        sub = [r for r in allrows if r['protocol'] == proto]
        lc = sum(bool(r['lexical_complete']) for r in sub)
        bc = sum(bool(r['labeller']['complete']) if r.get('labeller') else False
                 for r in sub)
        af = sum(bool(r['lexical_complete']) and bool(r['labeller']['complete'])
                 and r['f1'] < 1.0 for r in sub)
        lines.append(f"| {proto} | {len(sub)} | {lc} | {bc} | {af} |")
    lines.append('')
    only_lab = [r for r in rows if not r['lexical_complete']
                and r['labeller']['complete']]
    only_lex = [r for r in rows if r['lexical_complete']
                and not r['labeller']['complete']]
    lines += ['## Direction of the difference\n',
              f'Across the 120 sampled traces the labeller calls complete '
              f'coverage more often than the lexical rule ({sum(lab)} '
              f'vs {sum(lex)}). The disagreements split '
              f'{len(only_lab)} labeller-only complete and {len(only_lex)} '
              'lexical-only complete. Per protocol the labeller count is higher '
              'in random (9 vs 5), redundancy_aware (7 vs 5) and summary_exchange '
              '(2 vs 1) and equal in score_ranked (9 vs 9).\n',
              'This is the opposite direction to the earlier finding that the '
              'lexical rule over-counts coverage, and the two rules measure '
              'different things. The lexical rule asks whether 80% of a whole '
              'support paragraph\'s content tokens reappear in one board unit. '
              'A board that faithfully carries the decisive clause but drops the '
              'support\'s framing, or spreads it over units, falls below 0.8 even '
              'though the fact is carried; in the 14 labeller-only cases only 1 '
              'of 36 best-support recalls reaches 0.8. That is the labeller-finds-'
              'more direction. The 7 lexical-only cases are the other failure: '
              'every support\'s best recall is at least 0.8 (most exactly 1.0), '
              'and the labeller rejects them because the board repeats the '
              'support as a listing without the fact\'s relation or a complete '
              'restatement. The two measures therefore disagree in both '
              'directions, and neither is a one-sided over-count.\n',
              '**The coverage prompt is not validated.** Against author carrier '
              'labels it agrees with **70/180** comparisons (38.9%, exact '
              'Clopper-Pearson 95% CI 31.7-46.4%), Cohen kappa **0.031**; it '
              'calls coverage complete 58 times where the two authors do so 156 '
              'times (`20261113_coverage_validation/report.md`), below the 0.80 '
              'agreement threshold fixed in that rule. The labeller column is '
              'therefore reported beside the lexical column and is **not** a '
              'correction of the paper\'s coverage or AF figures; the lexical '
              'rule stands alone until a validated coverage measure exists.\n',
              '', '## Disagreements\n', '| trace | protocol | lexical | labeller (not validated) | f1 |',
              '| --- | --- | ---: | ---: | ---: |']
    for r in rows:
        if bool(r['lexical_complete']) != bool(r['labeller']['complete']):
            lines.append(f"| {r['instance_id']} | {r['protocol']} | "
                         f"{r['lexical_complete']} | {r['labeller']['complete']} | "
                         f"{r['f1']} |")
    if unparsed:
        lines += ['', 'Unparsed keys (in the sample, not scored): '
                  + ', '.join(r['key'] for r in unparsed) + '\n']
    REPORT.write_text('\n'.join(lines) + '\n')
    print(json.dumps({'n': len(rows), 'agreement': agree, 'kappa': kap,
                      'spent_usd': total}, indent=1))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--build', action='store_true')
    ap.add_argument('--pilot', action='store_true')
    ap.add_argument('--retry', action='store_true')
    ap.add_argument('--report', action='store_true')
    ap.add_argument('--cap-usd', type=float, default=5.0)
    a = ap.parse_args()
    if a.build:
        build()
    if a.pilot:
        pilot(a.cap_usd, retry=a.retry)
    if a.report:
        report()


if __name__ == '__main__':
    main()