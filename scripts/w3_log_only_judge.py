"""W3 log-only judge (rule `rebuttal/pilots/prereg/W3-log-only-judge-v1.md`).

Same judge model as the existing W3 judge row, log-only input view, stage read from the named log entry.

    ./.conda-env/bin/python -m scripts.w3_log_only_judge --build
    ./.conda-env/bin/python -m scripts.w3_log_only_judge --pilot        # 15 cases, cap $1.00
    ./.conda-env/bin/python -m scripts.w3_log_only_judge --run          # remaining 74, total cap $5.00
    ./.conda-env/bin/python -m scripts.w3_log_only_judge --score
"""
import argparse
import hashlib
import json
import math
from collections import Counter
from pathlib import Path

from scripts.missing_fact_repair_pilot import price
from utility.apis.base import APIRequest
from utility.apis.openrouter_api import single_request

ROOT = Path(__file__).resolve().parent.parent
RULE = ROOT / 'rebuttal/pilots/prereg/W3-log-only-judge-v1.md'
OUT = ROOT / 'rebuttal/pilots/20261116_w3_log_only_judge'
CASES = ROOT / 'rebuttal/pilots/20261113_attribution_comparison/cases_v2.json'
FULL = ROOT / 'rebuttal/pilots/20261113_attribution_comparison/results_v2.json'
ACCEPTED = ROOT / 'rebuttal/pilots/20261113_injected_distortion/accepted.json'
B6_CASES = ROOT / 'rebuttal/pilots/20261115_b6_repairs/cases.json'
PRICING = ROOT / 'rebuttal/pilots/20261108_preflight/pricing.json'
MODEL = 'google/gemini-3.6-flash'
MAX_OUT = 8192
TRUNC = 500
PILOT_CAP = 1.0
TOTAL_CAP = 5.0
PILOT_N = 15

MANIFEST = OUT / 'build_manifest.json'
CALLS = OUT / 'calls.jsonl'
RESULTS = OUT / 'results.jsonl'
SCORE = OUT / 'score.json'

# entry verb -> stage (the mapping in the rule file)
VERB_STAGE = {'received': 'sharding', 'produced': 'extraction', 'sent': 'transmission',
              'board': 'transmission', 'answer': 'aggregation'}


def sha_text(s):
    return hashlib.sha256(s.encode()).hexdigest()


def file_sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def system_prompt():
    """Read the system prompt verbatim from the frozen rule file."""
    text = RULE.read_text()
    block = text.split('## System prompt (sent verbatim)')[1].split('```')[1]
    return block.strip('\n')


def trunc(s, n=TRUNC):
    return s if len(s) <= n else s[:n] + ' ...'


def units_for(rows, agent):
    return '\n'.join(u['text'] for u in rows if u['agent_id'] == agent) or '(nothing)'


def agents_of(c):
    ids = {int(k) for k in c['source']}
    ids |= {u['agent_id'] for cp in ('extraction', 'transmission', 'board') for u in c[cp]}
    return sorted(ids)


def build_log(c):
    """Chronological log: (verb, agent, text). Stage labels are not in the rendered text."""
    entries = []
    for a in agents_of(c):
        entries.append(('received', a, c['source'].get(str(a), '(no shard)')))
        entries.append(('produced', a, units_for(c['extraction'], a)))
        entries.append(('sent', a, units_for(c['transmission'], a)))
    for u in c['board']:
        entries.append(('board', u['agent_id'], u['text']))
    entries.append(('answer', None, c['answer']))
    return entries


def render(c):
    lines = [f"QUESTION\n{c['question']}\n", 'RUN LOG']
    for k, (verb, a, text) in enumerate(build_log(c), 1):
        if verb == 'received':
            head = f'agent {a} received its input'
        elif verb == 'produced':
            head = f'agent {a} produced'
        elif verb == 'sent':
            head = f'agent {a} sent'
        elif verb == 'board':
            head = f'aggregator received from agent {a}'
        else:
            head = 'aggregator final answer (incorrect)'
        lines.append(f'[{k}] {head}: {trunc(text)}')
    return '\n'.join(lines)


def owners():
    """True owner agent per case key."""
    out = {}
    for a in json.loads(ACCEPTED.read_text())['accepted']:
        out[f"inj/{a['model']}/{a['instance_id']}"] = a['agent_id']
    for r in json.loads(B6_CASES.read_text()):
        src = r['source_ids'][0]  # 'gold:agent-N'
        out.setdefault(r['key'], int(src.split('agent-')[1]))
    return out


def load():
    cases = json.loads(CASES.read_text())
    full = {x['key']: x['judge']['stage'] for x in json.loads(FULL.read_text())['items']}
    own = owners()
    order = sorted(cases, key=lambda c: sha_text(c['key']))
    return order, full, own


def spent():
    if not CALLS.exists():
        return 0.0
    return sum(json.loads(l).get('cost_usd', 0) for l in CALLS.read_text().splitlines()
               if l.strip() and json.loads(l).get('event') == 'result')


def done_keys():
    if not RESULTS.exists():
        return set()
    return {json.loads(l)['key'] for l in RESULTS.read_text().splitlines() if l.strip()}


def build():
    OUT.mkdir(parents=True, exist_ok=True)
    order, full, own = load()
    missing = [c['key'] for c in order if c['key'] not in own]
    if missing:
        raise SystemExit(f'no owner for {missing[:3]}')
    pilot = [c['key'] for c in order[:PILOT_N]]
    man = {'recorded_before_any_call': True, 'rule': str(RULE.relative_to(ROOT)),
           'rule_sha256': file_sha(RULE), 'prompt_sha256': sha_text(system_prompt()),
           'model': MODEL, 'max_output_tokens': MAX_OUT, 'temperature': 0,
           'cases': len(order), 'pilot_keys': pilot, 'pilot_cap_usd': PILOT_CAP,
           'total_cap_usd': TOTAL_CAP, 'cases_sha256': file_sha(CASES)}
    MANIFEST.write_text(json.dumps(man, indent=1))
    print(json.dumps({k: man[k] for k in ('rule_sha256', 'prompt_sha256', 'cases', 'pilot_cap_usd')}))


def call(c, cap, total):
    system = system_prompt()
    user = render(c)
    pin, pout = price(MODEL)
    est_in = math.ceil((len(system) + len(user)) / 4)
    est = est_in * pin + MAX_OUT * pout
    if total + est > cap:
        with CALLS.open('a') as f:
            f.write(json.dumps({'event': 'skipped', 'key': c['key'], 'reason': 'cap',
                                'estimate_usd': round(est, 6)}) + '\n')
        return None
    cid = sha_text('|'.join([c['key'], system, user, str(MAX_OUT)]))
    with CALLS.open('a') as f:
        f.write(json.dumps({'event': 'intent', 'key': c['key'], 'call_id': cid, 'model': MODEL,
                            'system_sha256': sha_text(system), 'user_sha256': sha_text(user),
                            'max_tokens': MAX_OUT, 'temperature': 0}) + '\n')
    req = APIRequest(system_query=system, user_query=user, model=MODEL, max_tokens=MAX_OUT,
                     temperature=0, metadata={'pilot': 'w3_log_only_judge', 'key': c['key'],
                                              'openrouter_reasoning': True})
    resp = single_request(req)
    usage = resp.usage or {}
    cost = usage.get('prompt_tokens', est_in) * pin + usage.get('completion_tokens', 0) * pout
    with CALLS.open('a') as f:
        f.write(json.dumps({'event': 'result', 'key': c['key'], 'call_id': cid,
                            'success': resp.success, 'error': resp.error, 'content': resp.content,
                            'usage': usage, 'cost_usd': round(cost, 8)}) + '\n')
    return resp


def parse(content):
    if not content:
        return None
    t = content.strip()
    if t.startswith('```'):
        t = t.strip('`').split('\n', 1)[1] if '\n' in t else t.strip('`')
    try:
        obj = json.loads(t[t.index('{'):t.rindex('}') + 1])
        return {'entry': int(obj['entry']), 'agent': obj.get('agent'), 'reason': obj.get('reason', '')}
    except (ValueError, KeyError, TypeError):
        return None


def execute(keys_wanted, cap, label):
    order, full, own = load()
    by_key = {c['key']: c for c in order}
    done = done_keys()
    total = spent()
    stop = False
    for key in keys_wanted:
        if key in done:
            continue
        c = by_key[key]
        resp = call(c, cap, total)
        if resp is None:
            print(json.dumps({'stopped': 'cap', 'label': label, 'spent': round(total, 6)}))
            stop = True
            break
        total = spent()
        parsed = parse(resp.content) if resp.success else None
        entries = build_log(c)
        stage = None
        if parsed and 1 <= parsed['entry'] <= len(entries):
            stage = VERB_STAGE[entries[parsed['entry'] - 1][0]]
        rec = {'key': key, 'population': c['population'], 'known_stage': c['known_stage'],
               'parsed': parsed, 'mapped_stage': stage, 'correct': stage == c['known_stage'],
               'true_owner': own[key], 'last_agent': max(agents_of(c)),
               'full_trace_stage': full.get(key), 'success': resp.success, 'error': resp.error,
               'spend_total_usd': round(total, 6), 'label': label}
        with RESULTS.open('a') as f:
            f.write(json.dumps(rec) + '\n')
        print(json.dumps({'key': key, 'known': c['known_stage'], 'mapped': stage,
                          'entry': parsed and parsed['entry'], 'spend': round(total, 6)}))
    return stop


def pilot():
    man = json.loads(MANIFEST.read_text())
    execute(man['pilot_keys'], PILOT_CAP, 'pilot')


def run():
    man = json.loads(MANIFEST.read_text())
    if not all(k in done_keys() for k in man['pilot_keys']):
        raise SystemExit('pilot not complete; review it first')
    rest = [k for k in (c['key'] for c in load()[0]) if k not in man['pilot_keys']]
    execute(rest, TOTAL_CAP, 'full')


def wilson(k, n, z=1.959964):
    if n == 0:
        return None
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return [round(max(0, c - h), 3), round(min(1, c + h), 3)]


def score():
    recs = {}
    for l in RESULTS.read_text().splitlines():
        if l.strip():
            r = json.loads(l)
            recs[r['key']] = r
    rows = list(recs.values())
    n = len(rows)
    k = sum(r['correct'] for r in rows)
    ful = sum(1 for r in rows if r['full_trace_stage'] == r['known_stage'])
    named = [r for r in rows if r['parsed']]
    last_named = sum(1 for r in named if r['parsed']['agent'] == r['last_agent'])
    owner_last = sum(1 for r in rows if r['true_owner'] == r['last_agent'])
    out = {'n': n, 'correct': k, 'accuracy': round(k / n, 3) if n else None, 'wilson95': wilson(k, n),
           'full_trace_correct_same_cases': ful,
           'unparsed': n - len(named), 'named_agent_is_last': last_named,
           'named_agent_is_last_share': round(last_named / len(named), 3) if named else None,
           'true_owner_is_last_share': round(owner_last / n, 3) if n else None,
           'confusion': {f"{k} -> {m}": v for (k, m), v in Counter((r['known_stage'], r['mapped_stage']) for r in rows).items()},
           'spend_usd': round(spent(), 6), 'rule_sha256': json.loads(MANIFEST.read_text())['rule_sha256']}
    SCORE.write_text(json.dumps(out, indent=1, default=str))
    print(json.dumps(out, indent=1, default=str))


def main():
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument('--build', action='store_true')
    g.add_argument('--pilot', action='store_true')
    g.add_argument('--run', action='store_true')
    g.add_argument('--score', action='store_true')
    a = ap.parse_args()
    if a.build:
        build()
    elif a.pilot:
        pilot()
    elif a.run:
        run()
    else:
        score()


if __name__ == '__main__':
    main()
