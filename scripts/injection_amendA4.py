"""Injection experiment, amendment A4: extraction candidate expansion. Rule: prereg/Injection-v1-amendment-A4.md.

    ./.conda-env/bin/python -m scripts.injection_amendA4 --build
    nohup ./.conda-env/bin/python -m scripts.injection_amendA4 --run > rebuttal/pilots/20261115_injection_amendA4/run.log 2>&1 &

Extraction only. Candidates are the A3 extraction candidates extended to the uncapped pool (same plan, removal test,
exclusion of sharding candidates and order). A3 results are read as already tried; new cases go to the A4 folder.
Spend of all earlier logs counts toward the $4.00 cap (A3 carried in as a cache and spend).
"""
import argparse
import json
from pathlib import Path

import scripts.injection_experiment as X
import scripts.injection_amendA as A
import scripts.injection_amendA2 as A2
import scripts.injection_amendA3 as A3
from scripts.injection_amendA3 import plan_extraction_A3, COVER
from scripts.injection_experiment import MODELS, CAP, file_sha

ROOT = Path(__file__).resolve().parent.parent
RULE = ROOT / 'rebuttal/pilots/prereg/Injection-v1-amendment-A4.md'
OUT = ROOT / 'rebuttal/pilots/20261115_injection_amendA4'
A3_OUT = ROOT / 'rebuttal/pilots/20261115_injection_amendA3'
BUILD = OUT / 'build_manifest.json'
CALLS = OUT / 'calls.jsonl'
RESULTS = OUT / 'results.json'
CARRIED = [A3_OUT / 'calls.jsonl'] + A3.CARRIED
TARGET_KEPT = 30
MAX_ATTEMPTS_TYPE = 360


def build():
    OUT.mkdir(parents=True, exist_ok=True)
    a3 = json.loads((A3_OUT / 'build_manifest.json').read_text())
    el = X.eligible(A2.recs())
    cands = {}
    for m in MODELS:
        shard_inst = {c['instance'] for c in a3['candidates'][m]['sharding']}
        extr = []
        for inst in el[m]:
            if inst in shard_inst:
                continue
            if (p := plan_extraction_A3(A2.pkgs(m)[inst], A2.recs()[(m, inst)])):
                F = A2.content(p['fact'])
                left = [u['unit_id'] for u in A2.pkgs(m)[inst]['checkpoints']['extraction']
                        if u['unit_id'] not in set(p['unit_ids'])
                        and len(F & A2.content(u['text'])) / len(F) >= COVER]
                assert not left, (m, inst, left)
                extr.append({'model': m, 'instance': inst, 'type': 'extraction', 'plan': p})
        old = [c['instance'] for c in a3['candidates'][m]['extraction']]
        assert [c['instance'] for c in extr][:len(old)] == old, f'{m}: A3 list is not a prefix'
        cands[m] = extr
    seq = []
    for rank in range(max(len(v) for v in cands.values())):
        for m in MODELS:
            if rank < len(cands[m]):
                seq.append(cands[m][rank])
    order = [{'model': c['model'], 'instance': c['instance']} for c in seq][:MAX_ATTEMPTS_TYPE]
    new = [o for o in order if o['instance'] not in
           {c['instance'] for m in MODELS for c in a3['candidates'][m]['extraction']
            if c['model'] == o['model']}]
    man = {'recorded_before_any_call': True,
           'rule_file': str(RULE.relative_to(ROOT)), 'rule_sha256': file_sha(RULE),
           'code_file': str(Path(__file__).resolve().relative_to(ROOT)), 'code_sha256': file_sha(Path(__file__)),
           'a3_build_sha256': file_sha(A3_OUT / 'build_manifest.json'),
           'cap_usd': CAP, 'target_kept_per_type': TARGET_KEPT, 'max_attempts_per_type': MAX_ATTEMPTS_TYPE,
           'models': MODELS, 'candidates': {m: {'extraction': cands[m]} for m in MODELS},
           'pooled_order_extraction': order, 'new_candidates': new,
           'counts': {m: len(cands[m]) for m in MODELS}, 'pool_total': len(seq)}
    BUILD.write_text(json.dumps(man, indent=1, ensure_ascii=False))
    print(json.dumps({'counts': man['counts'], 'pool_total': man['pool_total'],
                      'new': [(o['model'], o['instance']) for o in new],
                      'rule_sha256': man['rule_sha256'], 'code_sha256': man['code_sha256']}, indent=1))


def run():
    man = json.loads(BUILD.read_text())
    assert file_sha(RULE) == man['rule_sha256'], 'rule changed'
    assert file_sha(Path(__file__)) == man['code_sha256'], 'code changed'
    ledger = A3.Ledger(CALLS, CAP, CARRIED)
    res = json.loads(RESULTS.read_text()) if RESULTS.exists() else {'cases': []}
    a3 = json.loads((A3_OUT / 'results.json').read_text())
    a3_extr = [r for r in a3['cases'] if r['type'] == 'extraction']
    done = {(r['model'], r['instance']) for r in a3_extr} | {(r['model'], r['instance']) for r in res['cases']}
    kept = sum(1 for r in a3_extr if r['kept'])
    tried = len(a3_extr)
    plans = {(c['model'], c['instance']): c for m in MODELS for c in man['candidates'][m]['extraction']}
    stopped = None
    try:
        for item in man['pooled_order_extraction']:
            if kept >= TARGET_KEPT or tried >= MAX_ATTEMPTS_TYPE:
                break
            m, inst = item['model'], item['instance']
            if (m, inst) in done:
                continue
            case = plans[(m, inst)]
            tried += 1
            trace, facts, f1, meta = A.make_case(m, inst, 'extraction', case['plan'], ledger)
            rec = {'model': m, 'instance': inst, 'type': 'extraction', 'plan': case['plan'],
                   'answer': trace['answer_text'], 'f1': f1, 'meta': meta, 'check': None, 'kept': False}
            if f1 < 1.0:
                rec['check'] = A2.residue(ledger, f'amA4-check/extraction/{m}/{inst}', trace, facts,
                                          case['plan']['fact_id'])
                rec['kept'] = rec['check']['status'] == 'ok' and not rec['check']['residual_units']
            if rec['kept']:
                rec['methods'] = X.methods(ledger, f'case/extraction/{m}/{inst}', trace, facts)
                kept += 1
            res['cases'].append(rec)
            done.add((m, inst))
            res['spend_usd'] = round(ledger.spent, 6)
            RESULTS.write_text(json.dumps(res, indent=1, ensure_ascii=False))
            print(json.dumps({'model': m, 'instance': inst, 'f1': round(f1, 3),
                              'kept': rec['kept'], 'kept_type': kept, 'tried_type': tried,
                              'spent': round(ledger.spent, 6)}), flush=True)
    except RuntimeError as e:
        stopped = str(e)
    print(json.dumps({'stopped': stopped, 'spend_usd_total_incl_earlier': round(ledger.spent, 6),
                      'kept_extraction_total': kept, 'tried_extraction_total': tried}, indent=1), flush=True)


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--build', action='store_true')
    ap.add_argument('--run', action='store_true')
    a = ap.parse_args()
    if a.build:
        build()
    if a.run:
        run()
