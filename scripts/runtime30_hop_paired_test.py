"""Paired exact (McNemar) test on the 26 scoreable traces: run-time agreement with facts as before vs hop-by-hop.

Stored outputs only, no calls. Before: rebuttal/pilots/20261116_runtime_30_rerun/score.json (merged rows).
After: rebuttal/pilots/20261116_runtime_30_hop/score.json (merged rows). Correct = merged stage equals gold stage.
"""
import json
from math import comb
from pathlib import Path

P = Path(__file__).resolve().parent.parent / 'rebuttal/pilots'


def mcnemar_exact(b, c):
    n, k = b + c, min(b, c)
    return min(1.0, 2 * sum(comb(n, i) for i in range(k + 1)) / 2 ** n)


if __name__ == '__main__':
    old = {r['instance']: r for r in json.loads((P / '20261116_runtime_30_rerun/score.json').read_text())['rows']}
    new = {r['instance']: r for r in json.loads((P / '20261116_runtime_30_hop/score.json').read_text())['rows']}
    keys = sorted(set(old) & set(new))
    assert len(keys) == 26, len(keys)
    ok_old = {k: old[k]['merged'] == old[k]['gold'] for k in keys}
    ok_new = {k: new[k]['merged'] == new[k]['gold'] for k in keys}
    both = sum(ok_old[k] and ok_new[k] for k in keys)
    old_only = sum(ok_old[k] and not ok_new[k] for k in keys)
    new_only = sum(ok_new[k] and not ok_old[k] for k in keys)
    neither = sum(not ok_old[k] and not ok_new[k] for k in keys)
    print(json.dumps({'n': len(keys), 'before_correct': sum(ok_old.values()), 'after_correct': sum(ok_new.values()),
                      'both': both, 'before_only': old_only, 'after_only': new_only, 'neither': neither,
                      'mcnemar_exact_two_sided_p': round(mcnemar_exact(old_only, new_only), 4)}, indent=1))
