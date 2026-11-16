"""Run-time 30-failure rerun (rule rebuttal/pilots/prereg/Runtime-30-rerun-v1.md, frozen before any call). Cap $2.00.

    .conda-env/bin/python scripts/runtime30_rerun.py --build    # no calls: inputs and hashes
    .conda-env/bin/python scripts/runtime30_rerun.py --pilot    # first 5 traces (5 calls)
    .conda-env/bin/python scripts/runtime30_rerun.py --price    # no calls: projection for the rest
    .conda-env/bin/python scripts/runtime30_rerun.py --run      # remaining traces, only if projected total < $2
    .conda-env/bin/python scripts/runtime30_rerun.py --score    # no calls
"""
import argparse
import hashlib
import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scripts.proxy_gold_merge import merge_stage, trace_stage, wilson  # noqa: E402
from utility.apis.base import APIRequest  # noqa: E402
from utility.apis.openrouter_api import single_request  # noqa: E402

P = ROOT / 'rebuttal/pilots'
OUT = P / '20261116_runtime_30_rerun'
RULE = P / 'prereg/Runtime-30-rerun-v1.md'
EQUIV_PROMPT = P / 'prereg/proxy_support_equiv_prompt_v1.json'
Q1 = P / '20261115_q1_second_sample'
MQ = P / '20261115_proxy_support_mq'
GAB = P / '20261116_gold_answer_bearing'
PLAN = GAB / 'plan.json'
GOLD_ROWS = GAB / 'results.jsonl'
GEMINI = 'google/gemini-3.6-flash'
PRICE = (0.75 / 1e6, 3.75 / 1e6)  # higher Gemini rate in proxy_support_run.py; used for the cap
CAP = 2.00
MAX_TOK = 3000
PILOT_N = 5
CALLS = OUT / 'calls.jsonl'
EQUIV = OUT / 'equiv.jsonl'
INPUTS = OUT / 'inputs.json'


def sha_file(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def spent():
    if not CALLS.exists():
        return 0.0
    return sum(json.loads(l).get('cost_usd', 0.0) for l in CALLS.read_text().splitlines()
               if l.strip() and json.loads(l).get('event') == 'result')


def build():
    assert not CALLS.exists(), 'refusing to freeze after calls exist'
    OUT.mkdir(parents=True, exist_ok=True)
    man_q1 = json.loads((Q1 / 'build_manifest.json').read_text())
    traces = man_q1['traces']
    q1_rows = [json.loads(l) for l in (Q1 / 'results.jsonl').read_text().splitlines() if l.strip()]
    pop = {r['instance_id']: r for r in json.loads((MQ / 'population.json').read_text())
           if r['protocol'] == 'random_relay'}
    facts = json.loads((MQ / 'facts.json').read_text())
    plan = {r['instance']: r for r in json.loads(PLAN.read_text())['rows']}
    gold_rows = [json.loads(l) for l in GOLD_ROWS.read_text().splitlines() if l.strip()]
    gem = [r for r in gold_rows if r['labeller'] == GEMINI]

    items, not_scoreable = [], []
    for inst in traces:
        pieces = plan[inst]['answer_bearing']
        ids = [f'a{i + 1}' for i in range(len(pieces))]
        g = {r['checkpoint']: r for r in gem if r['instance'] == inst}
        ext = g.get('extraction')
        if not pieces or ext is None or not ext['valid']:
            not_scoreable.append(inst)
            continue
        gold_labels = {'extraction': ext['atoms']}
        if not any(v == 'absent' for v in ext['atoms'].values()):
            # board is read only when no piece is absent at extraction (rule: Q1 amendment 1)
            if 'board' not in g or not g['board']['valid']:
                not_scoreable.append(inst)
                continue
            gold_labels['board'] = g['board']['atoms']
        p = pop[inst]
        f = facts.get(p['key']) or {}
        if f.get('status') != 'ok':
            not_scoreable.append(inst)
            continue
        recs = [r for r in q1_rows if r['instance'] == inst and r['kind'] == 'proxy' and r['valid']]
        proxy_labels = {r['fact_id']: r['stages'] for r in recs}
        proxy_atoms = {r['fact_id']: r['atoms'] for r in recs}
        proxy_facts = f['value']['facts']
        if set(proxy_labels) != {x['fact_id'] for x in proxy_facts}:
            not_scoreable.append(inst)
            continue
        items.append({'instance': inst, 'key': p['key'], 'question': p['question'],
                      'pieces': [{'id': i, 'text': t} for i, t in zip(ids, pieces)],
                      'gold_labels': gold_labels,
                      'proxy_facts': proxy_facts, 'proxy_labels': proxy_labels, 'proxy_atoms': proxy_atoms})
    INPUTS.write_text(json.dumps({'items': items, 'not_scoreable': not_scoreable}, indent=1, ensure_ascii=False))
    man = {'recorded_before_any_call': True, 'rule_sha256': sha_file(RULE),
           'equiv_prompt_sha256': sha_file(EQUIV_PROMPT), 'model': GEMINI, 'cap_usd': CAP,
           'facts_source': 'rebuttal/pilots/20261115_proxy_support_mq/facts.json (prompt v1, sha 1e654d00…)',
           'gold_source_sha256': sha_file(GOLD_ROWS), 'plan_sha256': sha_file(PLAN),
           'q1_manifest_sha256': sha_file(Q1 / 'build_manifest.json'), 'q1_results_sha256': sha_file(Q1 / 'results.jsonl'),
           'inputs_sha256': sha_file(INPUTS),
           'traces_listed': len(traces), 'scoreable': len(items), 'not_scoreable': not_scoreable,
           'scoreable_list': [x['instance'] for x in items]}
    (OUT / 'build_manifest.json').write_text(json.dumps(man, indent=1))
    print(json.dumps({k: v for k, v in man.items() if k != 'scoreable_list'}, indent=1))


def user_text(it, spec):
    facts = '\n'.join(f"{f['fact_id']}: {f['text']}" for f in it['proxy_facts'])
    supports = '\n'.join(f"[{p['id']}] {p['text']}" for p in it['pieces'])
    return spec['user'].format(question=it['question'], facts=facts, supports=supports)


def run_one(it, spec):
    user = user_text(it, spec)
    with CALLS.open('a') as f:
        f.write(json.dumps({'event': 'intent', 'instance': it['instance']}) + '\n')
    resp = single_request(APIRequest(system_query=spec['system'], user_query=user, model=GEMINI,
                                     max_tokens=MAX_TOK, temperature=0))
    u = resp.usage or {}
    pin, pout = u.get('prompt_tokens', 0), u.get('completion_tokens', 0)
    cost = pin * PRICE[0] + pout * PRICE[1]
    txt = resp.content or ''
    a, b = txt.find('{'), txt.rfind('}')
    parsed = None
    try:
        obj = json.loads(txt[a:b + 1])
        parsed = {x['fact_id']: {'verdict': x.get('verdict'), 'support_ids': x.get('support_ids') or []}
                  for x in obj['facts']}
    except Exception:
        parsed = None
    valid = parsed is not None and set(parsed) == {f['fact_id'] for f in it['proxy_facts']}
    with EQUIV.open('a') as f:
        f.write(json.dumps({'instance': it['instance'], 'equiv': parsed, 'valid': valid}) + '\n')
    with CALLS.open('a') as f:
        f.write(json.dumps({'event': 'result', 'instance': it['instance'], 'prompt_tokens': pin,
                            'completion_tokens': pout, 'cost_usd': round(cost, 8), 'valid': valid}) + '\n')
    return cost, valid


def done_set():
    if not EQUIV.exists():
        return set()
    return {json.loads(l)['instance'] for l in EQUIV.read_text().splitlines() if l.strip()}


def project(todo):
    pilot_costs = [json.loads(l)['cost_usd'] for l in CALLS.read_text().splitlines()
                   if l.strip() and json.loads(l).get('event') == 'result']
    mean = sum(pilot_costs) / len(pilot_costs)
    projected = spent() + mean * len(todo)
    print(json.dumps({'todo': len(todo), 'spent_so_far': round(spent(), 6), 'mean_cost_per_call': round(mean, 6),
                      'projected_total': round(projected, 6), 'cap': CAP}))
    return projected


def pilot_or_run(limit=None, only_if_affordable=False):
    man = json.loads((OUT / 'build_manifest.json').read_text())
    assert sha_file(RULE) == man['rule_sha256'], 'rule changed after hashing'
    assert sha_file(EQUIV_PROMPT) == man['equiv_prompt_sha256'], 'prompt changed after hashing'
    assert sha_file(INPUTS) == man['inputs_sha256'], 'inputs changed after hashing'
    spec = json.loads(EQUIV_PROMPT.read_text())
    items = json.loads(INPUTS.read_text())['items']
    done = done_set()
    todo = [it for it in items if it['instance'] not in done]
    if limit is not None:
        todo = todo[:limit]
    if only_if_affordable:
        if project(todo) >= CAP:
            print('NOT RUN: projected total is not under the cap'); return
    for it in todo:
        if spent() + 0.02 > CAP:  # per-call guard: no call is made if spend could pass the cap
            print(json.dumps({'stop': 'cap', 'spent': round(spent(), 6)})); return
        cost, valid = run_one(it, spec)
        print(json.dumps({'inst': it['instance'], 'valid': valid, 'cost': round(cost, 6),
                          'spent': round(spent(), 6)}), flush=True)
    print(json.dumps({'spent_total': round(spent(), 6), 'calls_logged': len([l for l in CALLS.read_text().splitlines()
                                                                           if '"result"' in l])}))


def price():
    man = json.loads((OUT / 'build_manifest.json').read_text())
    items = json.loads(INPUTS.read_text())['items']
    done = done_set()
    project([it for it in items if it['instance'] not in done])  # projection only, no calls


def score():
    items = json.loads(INPUTS.read_text())['items']
    eq = {}
    if EQUIV.exists():
        for l in EQUIV.read_text().splitlines():
            if l.strip():
                e = json.loads(l)
                eq[e['instance']] = (e['equiv'], e['valid'])
    rows = []
    for it in items:
        # gold stage: any piece absent at extraction -> extraction; else absent at board -> transmission
        ext = it['gold_labels']['extraction']
        if any(v == 'absent' for v in ext.values()):
            gold = 'extraction'
        elif any(v == 'absent' for v in it['gold_labels']['board'].values()):
            gold = 'transmission'
        else:
            gold = 'aggregation'
        equiv, valid = eq.get(it['instance'], (None, False))
        r = {'gold_support_ids': [p['id'] for p in it['pieces']], 'proxy_facts': it['proxy_facts'],
             'labels': it['proxy_labels']}
        unmerged = trace_stage(it['proxy_labels'])
        merged, ngroups = merge_stage(r, equiv if valid else None)
        rows.append({'instance': it['instance'], 'gold': gold, 'unmerged': unmerged, 'merged': merged,
                     'groups': ngroups, 'equiv_valid': valid})
    ran = [r for r in rows if r['equiv_valid']]
    n = len(rows)

    def rate(k, d):
        return {'k': k, 'n': d, 'rate': round(k / d, 3) if d else None,
                'wilson95': [round(x, 3) for x in wilson(k, d)[1:]] if d else None}

    out = {'scoreable': n, 'not_scoreable': json.loads(INPUTS.read_text())['not_scoreable'],
           'equiv_valid_traces': len(ran), 'spend_usd': round(spent(), 6), 'cap_usd': CAP}
    for name in ('unmerged', 'merged'):
        agree = sum(r['gold'] == r[name] for r in rows)
        alarms = [r for r in rows if r[name] in ('extraction', 'transmission')]
        real = [r for r in alarms if r['gold'] in ('extraction', 'transmission')]
        early = [r for r in rows if r['gold'] == 'extraction']
        caught = [r for r in early if r[name] == 'extraction']
        out[name] = {'agreement': rate(agree, n), 'alarms': len(alarms), 'alarm_real': rate(len(real), len(alarms)),
                     'early_gold': len(early), 'catch': rate(len(caught), len(early))}
    out['rows'] = rows
    (OUT / 'score.json').write_text(json.dumps(out, indent=1))
    print(json.dumps({k: v for k, v in out.items() if k != 'rows'}, indent=1))


def main():
    ap = argparse.ArgumentParser()
    for a in ('--build', '--pilot', '--price', '--run', '--score'):
        ap.add_argument(a, action='store_true')
    a = ap.parse_args()
    if a.build:
        build()
    if a.pilot:
        pilot_or_run(limit=PILOT_N)
    if a.price:
        price()
    if a.run:
        pilot_or_run(only_if_affordable=True)
    if a.score:
        score()


if __name__ == '__main__':
    main()
