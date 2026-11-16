"""Redundancy injection at k = 1 and k = 3 (v2). Rule: rebuttal/pilots/prereg/Redundancy-injection-k-v2.md.

Reuses the k = 2 pipeline (scripts/redundancy_injection.py) with K, rule, paths and cap overridden. $0 for build and score.

    ./.conda-env/bin/python -m scripts.redundancy_k_sweep --k 1 --build
    ./.conda-env/bin/python -m scripts.redundancy_k_sweep --k 1 --run     # calls; cap $2
    ./.conda-env/bin/python -m scripts.redundancy_k_sweep --k 1 --score   # $0
"""
import argparse
import json
import math
from pathlib import Path

import scripts.redundancy_injection as RI

ROOT = Path(__file__).resolve().parent.parent


def configure(k):
    out = ROOT / f'rebuttal/pilots/20261115_redundancy_k{k}'
    RI.K = k
    RI.RULE = ROOT / 'rebuttal/pilots/prereg/Redundancy-injection-k-v2.md'
    RI.OUT = out
    RI.BUILD = out / 'build_manifest.json'
    RI.CALLS = out / 'calls.jsonl'
    RI.RESULTS = out / 'results.json'
    RI.HANDCHECK = out / 'handcheck.md'
    RI.CAP_USD = 2.0
    return out


def wilson(k, n, z=1.96):
    if n == 0:
        return None
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return [round(max(0.0, c - h), 3), round(min(1.0, c + h), 3)]


def score(k):
    out = configure(k)
    res = json.loads((out / 'results.json').read_text())['cases']
    arms = ['base/score_ranked', 'duplicated/score_ranked', 'base/redundancy_aware', 'duplicated/redundancy_aware']
    rep = {'k': k, 'cases': len(res), 'arms': {}, 'paired': {}, 'duplicate_selected': {}}
    for a in arms:
        f1 = [r['arms'][a]['f1'] for r in res]
        ex = sum(1 for x in f1 if x >= 1.0)
        rep['arms'][a] = {'n': len(f1), 'exact': ex, 'exact_wilson95': wilson(ex, len(f1)),
                          'mean_f1': round(sum(f1) / len(f1), 3)}
        rep['duplicate_selected'][a] = sum(1 for r in res if r['arms'][a]['duplicate_selected'])
    for p in ('score_ranked', 'redundancy_aware'):
        pr = [(r['arms'][f'base/{p}']['f1'], r['arms'][f'duplicated/{p}']['f1']) for r in res]
        drop = sum(1 for b, d in pr if d < b)
        rise = sum(1 for b, d in pr if d > b)
        rep['paired'][p] = {'drop': drop, 'rise': rise, 'unchanged': len(pr) - drop - rise,
                            'mean_diff': round(sum(d - b for b, d in pr) / len(pr), 3)}
    (out / 'score.json').write_text(json.dumps(rep, indent=1))
    print(json.dumps(rep, indent=1))


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--k', type=int, required=True)
    ap.add_argument('--build', action='store_true')
    ap.add_argument('--run', action='store_true')
    ap.add_argument('--score', action='store_true')
    a = ap.parse_args()
    configure(a.k)
    if a.build:
        RI.build()
    if a.run:
        RI.run()
    if a.score:
        score(a.k)
