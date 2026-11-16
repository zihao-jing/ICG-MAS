"""A2: judge with the audit's fact table as extra input (step 39). Rule: rebuttal/pilots/prereg/Stage-naming-A2-judge-with-audit-v1.md.

    .conda-env/bin/python scripts/f39_a2_judge.py --build           # no calls: inputs and hashes
    .conda-env/bin/python scripts/f39_a2_judge.py --pilot           # 5 runs per backbone (10 calls)
    .conda-env/bin/python scripts/f39_a2_judge.py --full            # remaining runs, only after the pilot is priced
    .conda-env/bin/python scripts/f39_a2_judge.py --score           # no calls

Calls go through the injection Ledger (logs every call, tokens and cost) to
rebuttal/pilots/20261116_stage_naming/a2_calls.jsonl. Cap $10 for this run.
"""
import argparse
import hashlib
import json
import math
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import scripts.b5_attribution_2x2 as B  # noqa: E402
import scripts.injection_amendA as A  # noqa: E402
import scripts.injection_experiment as X  # noqa: E402
from scripts.answer_equiv import last_object  # noqa: E402

P = ROOT / 'rebuttal/pilots'
OUT = P / '20261116_stage_naming'
RULE = P / 'prereg/Stage-naming-A2-judge-with-audit-v1.md'
FACT_TABLES = OUT / 'fact_tables.json'
INPUTS = OUT / 'a2_inputs.json'
CALLS = OUT / 'a2_calls.jsonl'
RESULTS = OUT / 'a2_results.jsonl'
REPLAY = OUT / 'replay_calls.jsonl'  # copy of the A2 + A3 ledgers used to rebuild deleted-fact traces (no new spend)
CASES_V2 = P / '20261113_attribution_comparison/cases_v2.json'
JUDGE_PROMPT = P / '20261113_attribution_comparison/attribution_prompt_v1.json'
CAP = 10.0
STAGES = ('extraction', 'sharding', 'transmission', 'aggregation')
QWEN = X.QWEN
GEMINI = X.GEMINI


def sha(b):
    return hashlib.sha256(b).hexdigest()


def known_stage(row):
    return row['known_stage']


def evidence_block(row):
    st = row['audit_status']
    holders = ', '.join(row['holder_agents']) if row['holder_agents'] else 'none'
    return ('AUDIT EVIDENCE (the audit\'s fact table for this run; the fact below is the one the audit matched to the intended fact)\n'
            f"Fact: {row['matched_fact_text']}\n"
            f"Holding agent(s): {holders}\n"
            f"Audit status: extraction {st['extraction'] or ['absent']}; board {st['board'] or ['absent']}")


def base_user(row, spec, rebuild_ledger):
    """Judge user text exactly as the stored judge run built it (no evidence block)."""
    if row['population'] == 'injected':
        case = next(c for c in json.loads(CASES_V2.read_text()) if c['key'] == row['key'])
        return B.render_judge(spec, case)
    return judge_user(spec, trace_for(row, rebuild_ledger))


def trace_for(row, rebuild_ledger):
    res = json.loads((P / '20261115_injection_amendA3/results.json').read_text())
    c = next(x for x in res['cases'] if x.get('kept') in (True, 'True') and x['model'] == row['model']
             and x['instance'] == row['instance'])
    trace, _, _, _ = A.make_case(c['model'], c['instance'], c['type'], c['plan'], rebuild_ledger)
    return trace


def judge_user(spec, trace):
    return B.render_judge(spec, {
        'question': trace['question'],
        'source': {str(c['agent_id']): c['text'] for c in trace['source_contexts']},
        'extraction': trace['checkpoints']['extraction'],
        'transmission': trace['checkpoints']['transmission'],
        'board': trace['checkpoints']['board'],
        'answer': trace['answer_text']})


def build():
    assert not CALLS.exists(), 'refusing to freeze after calls exist'
    rows = json.loads(FACT_TABLES.read_text())
    matched = [r for r in rows if 'backbone' in r and 'excluded' not in r]
    spec = json.loads(JUDGE_PROMPT.read_text())
    rebuild = X.Ledger(REPLAY, 0.05)
    out = []
    for r in sorted(matched, key=lambda r: (r['backbone'], r['key'])):
        ev = evidence_block(r)
        user = base_user(r, spec, rebuild) + '\n\n' + ev
        out.append({'run_id': f"{r['backbone']}|{r['key']}", 'key': r['key'], 'backbone': r['backbone'],
                    'population': r['population'], 'known_stage': r['known_stage'],
                    'model': QWEN if r['backbone'] == 'qwen' else GEMINI,
                    'system_sha256': sha(spec['system'].encode()), 'user': user,
                    'user_sha256': sha(user.encode())})
    INPUTS.write_text(json.dumps(out, indent=1, ensure_ascii=False))
    man = {'recorded_before_any_call': True, 'rule_sha256': sha(RULE.read_bytes()),
           'judge_prompt_sha256': sha(JUDGE_PROMPT.read_bytes()), 'inputs_sha256': sha(INPUTS.read_bytes()),
           'runs': len(out), 'by_backbone': dict(Counter(o['backbone'] for o in out)),
           'replay_spend_usd': round(rebuild.spent, 6)}
    (OUT / 'a2_build_manifest.json').write_text(json.dumps(man, indent=1))
    print(json.dumps(man, indent=1))


def spent():
    if not CALLS.exists():
        return 0.0
    return sum(json.loads(l).get('cost_usd') or 0.0 for l in CALLS.read_text().splitlines()
               if l.strip() and json.loads(l).get('event') == 'result')


def run(which):
    man = json.loads((OUT / 'a2_build_manifest.json').read_text())
    assert sha(RULE.read_bytes()) == man['rule_sha256'], 'rule changed after hashing'
    assert sha(INPUTS.read_bytes()) == man['inputs_sha256'], 'inputs changed after hashing'
    items = json.loads(INPUTS.read_text())
    if which == 'pilot':
        pick = []
        for bb in ('qwen', 'gemini'):
            pick += [i for i in items if i['backbone'] == bb][:5]
    else:
        done = set()
        if RESULTS.exists():
            done = {json.loads(l)['run_id'] for l in RESULTS.read_text().splitlines() if l.strip()}
        pick = [i for i in items if i['run_id'] not in done]
    ledger = X.Ledger(CALLS, CAP)
    for it in pick:
        verdict_raw = ledger.call(f"a2/{it['run_id']}", it['model'],
                                  [{'role': 'system', 'content': json.loads(JUDGE_PROMPT.read_text())['system']},
                                   {'role': 'user', 'content': it['user']}], max_tokens=2048)
        obj = last_object(verdict_raw or '')
        st = str((obj or {}).get('stage', '')).lower()
        stage = st if st in STAGES else None
        rec = {'run_id': it['run_id'], 'key': it['key'], 'backbone': it['backbone'], 'population': it['population'],
               'known_stage': it['known_stage'], 'judge_with_audit': stage, 'raw': verdict_raw}
        with RESULTS.open('a') as f:
            f.write(json.dumps(rec, ensure_ascii=False) + '\n')
        print(json.dumps({'run': it['run_id'][:60], 'stage': stage, 'known': it['known_stage'],
                          'spent': round(ledger.spent, 6)}), flush=True)
    print(json.dumps({'spent_total': round(spent(), 6), 'calls_this_run': len(pick)}))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--build', action='store_true')
    ap.add_argument('--pilot', action='store_true')
    ap.add_argument('--full', action='store_true')
    a = ap.parse_args()
    if a.build:
        build()
    if a.pilot:
        run('pilot')
    if a.full:
        run('full')


if __name__ == '__main__':
    main()
