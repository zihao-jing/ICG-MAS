"""A2 on all 82 known-cause runs (step 46). Rule: rebuttal/pilots/prereg/Stage-naming-A2-all82-v1.md.

    python3 scripts/f39_a2_all82.py --build     # no calls: inputs and hashes
    python3 scripts/f39_a2_all82.py --pilot     # 10 calls (5 per backbone, new runs only)
    python3 scripts/f39_a2_all82.py --full      # remaining new runs, only after the pilot is priced
    python3 scripts/f39_a2_all82.py --score     # no calls

Reuses the judge prompt, renderer and parser of f39_a2_judge.py. The 51 runs already in a2_results.jsonl
are kept and not called again. Calls go through the injection Ledger to a2_calls_all82.jsonl (cap $1.00).
"""
import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import scripts.f39_a2_judge as J  # noqa: E402  (judge prompt, renderer, evidence wording, parser)
import scripts.injection_experiment as X  # noqa: E402
from scripts.answer_equiv import last_object  # noqa: E402
from scripts.b5_attribution_2x2 import render_judge  # noqa: E402

P = ROOT / 'rebuttal/pilots'
OUT = P / '20261116_stage_naming'
RULE = P / 'prereg/Stage-naming-A2-all82-v1.md'
FACT_STRICT = OUT / 'fact_tables_strict.json'
INPUTS = OUT / 'a2_inputs_all82.json'
MANIFEST = OUT / 'a2_build_manifest_all82.json'
CALLS = OUT / 'a2_calls_all82.jsonl'
RESULTS = OUT / 'a2_results_all82.jsonl'
OLD_RESULTS = OUT / 'a2_results.jsonl'
OLD_INPUTS = OUT / 'a2_inputs.json'
CAP = 1.0
STAGES = J.STAGES


def sha(b):
    return hashlib.sha256(b).hexdigest()


def fact_index():
    rows = json.loads(FACT_STRICT.read_text())
    return {(r['backbone'], r['key']): r for r in rows if 'backbone' in r}


def block(row):
    if row and row.get('matched_fact_id'):
        return J.evidence_block(row)
    return ('AUDIT EVIDENCE (the audit\'s fact table for this run; the audit matched no fact to the intended fact)\n'
            'Fact: none\nHolding agent(s): none\nAudit status: none')


def all_runs():
    """82 known-cause runs: injected and deleted cases under both backbones (from the stored judge outputs)."""
    q = json.loads((P / '20261115_b5_attribution_2x2/judge_qwen.json').read_text())['items']
    g = json.loads((P / '20261113_attribution_comparison/results_v2.json').read_text())['items']
    inj = [x for x in q if x['population'] == 'injected']
    inj_g = {x['key'] for x in g if x['population'] == 'injected'}
    assert {x['key'] for x in inj} == inj_g, 'injected key sets differ between qwen and gemini judge files'
    runs = []
    for x in inj:
        for bb in ('qwen', 'gemini'):
            runs.append({'backbone': bb, 'key': x['key'], 'population': 'injected',
                         'known_stage': x['known_stage']})
    # deleted-fact runs: the audit's fact table rows (11 cases x 2 backbones)
    for r in json.loads(FACT_STRICT.read_text()):
        if r.get('population') == 'deleted' and 'backbone' in r:
            runs.append({'backbone': r['backbone'], 'key': r['key'], 'population': 'deleted',
                         'known_stage': r['known_stage']})
    return runs


def build():
    assert not CALLS.exists(), 'refusing to freeze after calls exist'
    runs = all_runs()
    assert len(runs) == 82, len(runs)
    old_done = {json.loads(l)['run_id'] for l in OLD_RESULTS.read_text().splitlines() if l.strip()}
    spec = json.loads(J.JUDGE_PROMPT.read_text())
    idx = fact_index()
    cases = {c['key']: c for c in json.loads(J.CASES_V2.read_text())}
    rebuild = X.Ledger(J.REPLAY, 0.05)
    out = []
    for r in sorted(runs, key=lambda r: (r['backbone'], r['key'])):
        run_id = f"{r['backbone']}|{r['key']}"
        if run_id in old_done:
            continue  # already done in A2 (51 runs); not called again
        if r['population'] == 'injected':
            user = render_judge(spec, cases[r['key']])
        else:
            _, _, model, instance = r['key'].split('/')  # case/<type>/<model>/<instance>
            user = J.judge_user(spec, J.trace_for({'model': model, 'instance': instance}, rebuild))
        row = idx.get((r['backbone'], r['key']))
        user = user + '\n\n' + block(row)
        out.append({'run_id': run_id, 'key': r['key'], 'backbone': r['backbone'], 'population': r['population'],
                    'known_stage': r['known_stage'],
                    'model': X.QWEN if r['backbone'] == 'qwen' else X.GEMINI,
                    'matched': bool(row and row.get('matched_fact_id')),
                    'system_sha256': sha(spec['system'].encode()), 'user': user,
                    'user_sha256': sha(user.encode())})
    INPUTS.write_text(json.dumps(out, indent=1, ensure_ascii=False))
    man = {'recorded_before_any_call': True, 'rule_sha256': sha(RULE.read_bytes()),
           'judge_prompt_sha256': sha(J.JUDGE_PROMPT.read_bytes()), 'inputs_sha256': sha(INPUTS.read_bytes()),
           'new_runs': len(out), 'already_done_runs': len(old_done),
           'new_by_backbone': {bb: sum(1 for o in out if o['backbone'] == bb) for bb in ('qwen', 'gemini')},
           'new_matched': sum(1 for o in out if o['matched']),
           'replay_spend_usd': round(rebuild.spent, 6)}
    MANIFEST.write_text(json.dumps(man, indent=1))
    print(json.dumps(man, indent=1))


def run(which):
    man = json.loads(MANIFEST.read_text())
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
    system = json.loads(J.JUDGE_PROMPT.read_text())['system']
    for it in pick:
        raw = ledger.call(f"a2all82/{it['run_id']}", it['model'],
                          [{'role': 'system', 'content': system}, {'role': 'user', 'content': it['user']}],
                          max_tokens=2048)
        obj = last_object(raw or '')
        st = str((obj or {}).get('stage', '')).lower()
        stage = st if st in STAGES else None
        rec = {'run_id': it['run_id'], 'key': it['key'], 'backbone': it['backbone'], 'population': it['population'],
               'known_stage': it['known_stage'], 'matched': it['matched'], 'judge_with_audit': stage, 'raw': raw}
        with RESULTS.open('a') as f:
            f.write(json.dumps(rec, ensure_ascii=False) + '\n')
        print(json.dumps({'run': it['run_id'][:60], 'stage': stage, 'known': it['known_stage'],
                          'spent_so_far': round(ledger.spent, 6)}), flush=True)
    print(json.dumps({'calls_this_run': len(pick), 'spent_total_this_step': round(ledger.spent, 6)}))


def wilson(k, n, z=1.96):
    if n == 0:
        return (0.0, 0.0)
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * ((p * (1 - p) + z * z / (4 * n)) / n) ** 0.5 / d
    return (round(c - h, 3), round(c + h, 3))


def correct(rec):
    if rec['population'] == 'injected':
        return rec['judge_with_audit'] == 'transmission'
    return rec['judge_with_audit'] == rec['known_stage']


def score():
    rows = {}
    for l in OLD_RESULTS.read_text().splitlines():
        if l.strip():
            r = json.loads(l)
            rows[r['run_id']] = {**r, 'matched': None}
    for l in RESULTS.read_text().splitlines() if RESULTS.exists() else []:
        if l.strip():
            r = json.loads(l)
            rows[r['run_id']] = r
    assert len(rows) == 82, f'have {len(rows)} judge+audit results, need 82'
    k = sum(correct(r) for r in rows.values())
    out = {'judge_with_audit_82': {'k': k, 'n': 82, 'rate': round(k / 82, 3), 'wilson95': wilson(k, 82)},
           'by_backbone': {bb: {'k': sum(correct(r) for r in rows.values() if r['backbone'] == bb),
                                'n': sum(1 for r in rows.values() if r['backbone'] == bb)} for bb in ('qwen', 'gemini')},
           'spent_this_step': round(sum(json.loads(l).get('cost_usd') or 0 for l in CALLS.read_text().splitlines()
                                        if l.strip() and json.loads(l).get('event') == 'result'), 6)
           if CALLS.exists() else 0.0}
    (OUT / 'a2_score_all82.json').write_text(json.dumps(out, indent=1))
    print(json.dumps(out, indent=1))


def main():
    ap = argparse.ArgumentParser()
    for flag in ('--build', '--pilot', '--full', '--score'):
        ap.add_argument(flag, action='store_true')
    a = ap.parse_args()
    if a.build:
        build()
    if a.pilot:
        run('pilot')
    if a.full:
        run('full')
    if a.score:
        score()


if __name__ == '__main__':
    main()
