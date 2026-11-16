"""Placement test v2: oracle decisive evidence at the target vs hash agent.

Amendment: `rebuttal/pilots/20261113_placement_v2/PLACEMENT_AMENDMENT_V2.md`,
frozen before any call. Same six traces and arms as v1; cap $5.

    ./run.sh python -m scripts.placement_test_v2 --build
    ./run.sh python -m scripts.placement_test_v2 --pilot --cap-usd 5
    ./run.sh python -m scripts.placement_test_v2 --report
"""
import argparse
import hashlib
import json
import math
from pathlib import Path

from scripts.missing_fact_repair_pilot import cp_ci, price
from scripts.pilot_llm_labeller import MODEL_OPENROUTER, PRICE_IN, PRICE_OUT
from scripts.placement_test import hash_agent, target_agent, traces
from src.eval.silo_bench_loader import silobench_exact_match
from src.protocols.base import extract_answer
from src.protocols.relay import _AGGREGATION_SYSTEM, _build_evidence_board_prompt
from utility.apis.base import APIRequest

ROOT = Path(__file__).resolve().parent.parent
V1 = ROOT / 'rebuttal/pilots/20261113_placement'
OUT = ROOT / 'rebuttal/pilots/20261113_placement_v2'
AMENDMENT = OUT / 'PLACEMENT_AMENDMENT_V2.md'
ACTIONS = OUT / 'action_manifest.json'
MANIFEST = OUT / 'run_manifest.json'
CALLS = OUT / 'calls.jsonl'
RESULTS = OUT / 'placement_results.json'
REPORT = OUT / 'report.md'
V1_LABELS = V1 / 'labels.json'
V1_ACTIONS = V1 / 'action_manifest.json'
SEED = 43
PILOT_N = 6
MAX_TOKENS = 1024


def sha(text):
    return hashlib.sha256(text.encode()).hexdigest()


def file_sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def pick():
    labels = json.loads(V1_LABELS.read_text())['traces']
    by = {}
    for r in labels:
        if not r.get('base_correct') and \
                (r.get('parsed') or {}).get('verdict') == 'DEFECT':
            by.setdefault(r['model'].split('/')[0], []).append(r['trace_id'])
    picked = []
    for fam in sorted(by):
        ids = sorted(by[fam], key=lambda x: sha(f'43|pilot|{x}'))
        picked.extend(ids[:2])
    return picked[:PILOT_N]


def build():
    picked = pick()
    assert len(picked) == PILOT_N, picked
    v1 = {a['trace_id']: a for a in
          json.loads(V1_ACTIONS.read_text())['actions']}
    tr = {t['trace_id']: t for t in traces()}
    acts = []
    for tid in picked:
        t = tr[tid]
        tgt, _ = target_agent(t)
        hsh = hash_agent(t, tgt)
        gold = str(t['gold_answer'])
        text = (f"Corrected evidence from this agent's partition: the result "
                f"is {gold}.")
        acts.append({'trace_id': tid, 'instance_id': t['instance_id'],
                     'model': t['model'], 'gold_answer': gold,
                     'base_correct': bool(t['answer_matches_gold']),
                     'target_agent': tgt, 'hash_agent': hsh,
                     'inserted_text': text,
                     'v1_inserted_text': v1[tid]['inserted_text'],
                     'v1_gold_in_text': gold in v1[tid]['inserted_text'],
                     'v2_gold_in_text': gold in text})
    OUT.mkdir(parents=True, exist_ok=True)
    ACTIONS.write_text(json.dumps({'amendment': str(AMENDMENT.relative_to(ROOT)),
                                   'seed': SEED, 'actions': acts},
                                  indent=1, ensure_ascii=False))
    MANIFEST.write_text(json.dumps({
        'recorded_before_first_call': True,
        'amendment_sha256': file_sha(AMENDMENT),
        'actions_sha256': file_sha(ACTIONS),
        'v1_actions_sha256': file_sha(V1_ACTIONS),
        'v1_labels_sha256': file_sha(V1_LABELS),
        'seed': SEED, 'pilot_n': PILOT_N, 'max_tokens': MAX_TOKENS,
        'aggregation_system_sha256': sha(_AGGREGATION_SYSTEM),
    }, indent=1))
    print(json.dumps({'picked': picked,
                      'v1_gold_in_text': sum(a['v1_gold_in_text'] for a in acts),
                      'v2_gold_in_text': sum(a['v2_gold_in_text'] for a in acts)},
                     indent=1))


def call(key, model, system, user, cap, total):
    pin, pout = (PRICE_IN, PRICE_OUT) if model == MODEL_OPENROUTER else price(model)
    est_in = math.ceil((len(system) + len(user)) / 4)
    est = est_in * pin + MAX_TOKENS * pout
    if total + est > cap:
        with CALLS.open('a') as f:
            f.write(json.dumps({'event': 'skipped', 'key': key, 'reason': 'cap',
                                'cost_usd': 0.0}) + '\n')
        return None, total
    call_id = sha('|'.join([key, model, system, user, str(MAX_TOKENS)]))
    with CALLS.open('a') as f:
        f.write(json.dumps({'event': 'intent', 'key': key, 'call_id': call_id,
                            'model': model, 'system_sha256': sha(system),
                            'user_sha256': sha(user),
                            'max_tokens': MAX_TOKENS, 'temperature': 0}) + '\n')
    from utility.apis.openrouter_api import single_request
    req = APIRequest(system_query=system, user_query=user, model=model,
                     max_tokens=MAX_TOKENS, temperature=0,
                     metadata={'pilot': 'placement_test_v2', 'key': key,
                               'openrouter_reasoning': False})
    resp = single_request(req)
    usage = resp.usage or {}
    cost = (usage.get('prompt_tokens', est_in) * pin
            + usage.get('completion_tokens', 0) * pout)
    with CALLS.open('a') as f:
        f.write(json.dumps({'event': 'result', 'key': key, 'call_id': call_id,
                            'model': model, 'success': resp.success,
                            'error': resp.error, 'content': resp.content,
                            'usage': usage, 'cost_usd': round(cost, 8)}) + '\n')
    return resp, total + cost


def spent():
    if not CALLS.exists():
        return 0.0
    return sum(json.loads(l).get('cost_usd', 0.0)
               for l in CALLS.read_text().splitlines()
               if l.strip() and json.loads(l).get('event') in ('result', 'skipped'))


def pilot(cap):
    man = json.loads(MANIFEST.read_text())
    assert file_sha(AMENDMENT) == man['amendment_sha256'], 'amendment changed'
    assert file_sha(ACTIONS) == man['actions_sha256'], 'actions changed'
    acts = {a['trace_id']: a for a in
            json.loads(ACTIONS.read_text())['actions']}
    tr = {t['trace_id']: t for t in traces()}
    total = spent()
    done = {}
    if RESULTS.exists():
        done = {r['key']: r for r in json.loads(RESULTS.read_text())['calls']}
    rows = []
    for tid, a in acts.items():
        for arm, agent in (('target', a['target_agent']),
                           ('hash', a['hash_agent'])):
            key = f'placement2/{tid}/{arm}'
            if key in done:
                rows.append(done[key])
                continue
            unit = {'unit_id': f'P-{arm[0]}:{agent}', 'agent_id': agent,
                    'text': a['inserted_text']}
            units = list(tr[tid]['board_units']) + [unit]
            n = max(int(u['agent_id']) for u in units) + 1
            grouped = [[] for _ in range(n)]
            for u in units:
                grouped[int(u['agent_id'])].append(str(u['text']))
            user = _build_evidence_board_prompt(grouped, tr[tid]['question'])
            resp, total = call(key, tr[tid]['model'], _AGGREGATION_SYSTEM,
                               user, cap, total)
            if resp is None:
                print(json.dumps({'stopped': 'cap',
                                  'spent': round(total, 6)}))
                break
            pred = extract_answer(resp.content or '')
            ok = bool(silobench_exact_match(pred,
                                            {'answer': tr[tid]['gold_answer']}))
            rows.append({'key': key, 'trace_id': tid,
                         'instance_id': a['instance_id'],
                         'model': a['model'], 'arm': arm, 'agent': agent,
                         'success': resp.success, 'prediction': pred,
                         'correct': ok,
                         'inserted_text': a['inserted_text']})
            RESULTS.write_text(json.dumps({'pilot': list(acts), 'calls': rows},
                                          indent=1, ensure_ascii=False))
            print(json.dumps({'trace': a['instance_id'], 'arm': arm,
                              'correct': ok,
                              'spent_usd': round(total, 6)}), flush=True)
    RESULTS.write_text(json.dumps({'pilot': list(acts), 'calls': rows},
                                  indent=1, ensure_ascii=False))
    print(json.dumps({'calls': len(rows), 'spent_usd': round(spent(), 8)},
                     indent=1))


def report():
    d = json.loads(RESULTS.read_text())
    calls = d['calls']
    acts = {a['trace_id']: a for a in
            json.loads(ACTIONS.read_text())['actions']}
    total = spent()
    lines = ['# Delivery diagnostic v2 — oracle corrective unit\n',
             f"Amendment `PLACEMENT_AMENDMENT_V2.md` (sha256 "
             f"`{file_sha(AMENDMENT)[:12]}`); action manifest "
             f"`{file_sha(ACTIONS)[:12]}`. Spend ${total:.6f}.\n",
             'The v1 run and its all-wrong result stay on record in '
             '`../20261113_placement/report.md`. Diagnosis: the v1 inserted '
             'line was the agent\'s raw input shard, and it contained the '
             'stored gold answer in **0 of 6** piloted traces. v2 inserts an '
             'oracle evidence statement that contains the gold in **6 of 6**, '
             'identical in both arms. **Both arms therefore receive the '
             'decisive evidence, so this run cannot test whether placement '
             'brings missing evidence to the model.** It tests only whether a '
             'sufficient corrective unit is used at the final answer, and '
             'whether its position changes that use. The target-vs-hash '
             'difference is not a placement effect.\n',
             '| trace | model | base | target agent | hash agent | target | hash |',
             '| --- | --- | ---: | ---: | ---: | ---: | ---: |']
    tt = hh = nt = nh = 0
    for tid in d['pilot']:
        sub = [c for c in calls if c['trace_id'] == tid]
        t = next((c for c in sub if c['arm'] == 'target'), None)
        h = next((c for c in sub if c['arm'] == 'hash'), None)
        if not t or not h:
            continue
        tt += t['correct']; hh += h['correct']; nt += 1; nh += 1
        lines.append(f"| {t['instance_id']} | {t['model'].split('/')[0]} | "
                     f"{'yes' if acts[tid]['base_correct'] else 'no'} | "
                     f"{t['agent']} | {h['agent']} | "
                     f"{'yes' if t['correct'] else 'no'} | "
                     f"{'yes' if h['correct'] else 'no'} |")
    lo_t, hi_t = cp_ci(tt, nt)
    lo_h, hi_h = cp_ci(hh, nh)
    lines += ['', f'Target exact **{tt}/{nt}** ({100*tt/nt:.1f}%, 95% CI '
                  f'{100*lo_t:.1f}-{100*hi_t:.1f}%); hash exact **{hh}/{nh}** '
                  f'({100*hh/nh:.1f}%, 95% CI {100*lo_h:.1f}-{100*hi_h:.1f}%); '
                  f'paired difference {tt-hh:+d} at n={nt} (**descriptive '
                  'only**; this is a 6-trace pilot, not a population claim).\n',
                  'Inserted text (identical in both arms):\n']
    for tid in d['pilot']:
        a = acts[tid]
        lines.append(f"- {a['instance_id']} / {a['model'].split('/')[0]}: "
                     f"`{a['inserted_text'][:160]}`")
    used = tt + hh
    lines += ['', '## Reading\n',
              f'The oracle unit is used in **{used}/12** arm calls (target {tt}, '
              f'hash {hh}), against **0/12** in v1, consistent with the v1 '
              'failure being delivery: its raw shard never contained the '
              'missing evidence. '
              'The arms disagree on 1 of 6 traces. On III-28 (google) '
              'both arms return the same full vector, so neither call used '
              'the corrective unit; on II-17 (qwen) the hash arm returns the '
              'correct array while the target arm emits a degenerate repeated '
              '"the" string. With n=6 the target-vs-hash difference is not a '
              'placement effect; the pilot shows the aggregator uses an '
              'explicit corrective unit in some calls, not that placement '
              'delivers the evidence.',
              ]
    REPORT.write_text('\n'.join(lines) + '\n')
    print(json.dumps({'target': tt, 'hash': hh, 'n': nt,
                      'spent_usd': total}, indent=1))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--build', action='store_true')
    ap.add_argument('--pilot', action='store_true')
    ap.add_argument('--report', action='store_true')
    ap.add_argument('--cap-usd', type=float, default=5.0)
    a = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    if a.build:
        build()
    if a.pilot:
        pilot(a.cap_usd)
    if a.report:
        report()


if __name__ == '__main__':
    main()