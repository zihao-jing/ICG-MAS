"""Zero-cost check of extraction removal: does removing the units the base labeller marked faithful
(A2 rule) leave lexical copies of the anchor fact in the extraction pool? Also tests the A3 rule
(base-faithful units plus every pool unit with fact coverage >= COVER).

    ./.conda-env/bin/python -m scripts.injection_removal_check
Output: rebuttal/pilots/20261115_injection_removal_test/removal_check.json
No model calls.
"""
import json
from pathlib import Path

import scripts.injection_amendA2 as A2
from scripts.injection_experiment import MODELS

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'rebuttal/pilots/20261115_injection_removal_test'
BUILD = ROOT / 'rebuttal/pilots/20261115_injection_amendA2/build_manifest.json'


def copies(pkg, fact_text, removed):
    F = A2.content(fact_text)
    out = []
    for u in pkg['checkpoints']['extraction']:
        if u['unit_id'] in removed or not F:
            continue
        cov = len(F & A2.content(u['text'])) / len(F)
        if cov >= A2.COVER:
            out.append({'unit_id': u['unit_id'], 'coverage': round(cov, 3)})
    return out


def lexical_units(pkg, fact_text):
    return {c['unit_id'] for c in copies(pkg, fact_text, set())}


def main():
    man = json.loads(BUILD.read_text())
    rows = []
    for m in MODELS:
        pk = A2.pkgs(m)
        for c in man['candidates'][m]['extraction']:
            inst, plan = c['instance'], c['plan']
            pkg = pk[inst]
            base = set(plan['unit_ids'])
            left_a2 = copies(pkg, plan['fact'], base)
            left_a3 = copies(pkg, plan['fact'], base | lexical_units(pkg, plan['fact']))
            rows.append({'model': m, 'instance': inst, 'fact_id': plan['fact_id'],
                         'base_removed': sorted(base), 'copies_left_A2': left_a2,
                         'copies_left_A3': left_a3})
    OUT.mkdir(parents=True, exist_ok=True)
    summary = {'extraction_candidates_checked': len(rows),
               'by_model': {m: sum(1 for r in rows if r['model'] == m) for m in MODELS},
               'with_copy_left_after_A2': sum(1 for r in rows if r['copies_left_A2']),
               'with_2plus_copies_left_after_A2': sum(1 for r in rows if len(r['copies_left_A2']) >= 2),
               'with_copy_left_after_A3': sum(1 for r in rows if r['copies_left_A3'])}
    (OUT / 'removal_check.json').write_text(json.dumps({'summary': summary, 'rows': rows}, indent=1))
    print(json.dumps(summary, indent=1))
    for r in [r for r in rows if len(r['copies_left_A2']) >= 2][:3]:
        print(json.dumps(r))


if __name__ == '__main__':
    main()
