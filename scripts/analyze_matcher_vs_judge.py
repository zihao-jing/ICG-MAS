"""T02 source: frozen matcher against the reference judge on the 80-instance held-out set.

Reads only the saved matcher (`E4_pool_matcher/matcher`) and judge (`E1_judge_sealed/outputs`)
outputs. Binary = correct vs any defect class. No author label is used here; the note in T02 says
so. Percentile instance-cluster bootstrap, 2,000 draws, seed 42.

    python -m scripts.analyze_matcher_vs_judge
"""
import json
from collections import Counter, defaultdict
from pathlib import Path

from src.audit.pilot_common import cluster_bootstrap

JUDGE = Path('rebuttal/results/batch1/E1_judge_sealed/outputs')
MATCHER = Path('rebuttal/results/batch1/E4_pool_matcher/matcher')
OUT = Path('rebuttal/results/batch1/E1/matcher_vs_judge_80.json')
DRAWS, SEED = 2000, 42
DEFECTS = ('reached_but_unused', 'lost', 'exclude_partial')


def kappa(rows):
    n = len(rows)
    ca, cb = Counter(r['a'] for r in rows), Counter(r['b'] for r in rows)
    po = sum(r['a'] == r['b'] for r in rows) / n
    pe = sum(ca[k] * cb[k] for k in set(ca) | set(cb)) / n ** 2
    return None if abs(1 - pe) < 1e-12 else (po - pe) / (1 - pe)


def main():
    judge = {}
    for p in JUDGE.glob('*.json'):
        d = json.loads(p.read_text())
        if d.get('valid') and (d.get('parsed') or {}).get('binary_call'):
            judge[(d['instance_id'], d['model'])] = d['parsed']['binary_call']
    matcher = {}
    for p in MATCHER.glob('*.json'):
        d = json.loads(p.read_text())
        if d.get('status') == 'ok' and d.get('trace_call'):
            matcher[(d['instance_id'], d['model'])] = d['trace_call']
    keys = sorted(set(judge) & set(matcher))
    rows3 = [{'instance_id': i, 'a': matcher[(i, m)], 'b': judge[(i, m)]} for i, m in keys]
    binr = lambda x: 'correct' if x == 'correct' else 'defect'
    rows2 = [{'instance_id': r['instance_id'], 'a': binr(r['a']), 'b': binr(r['b'])} for r in rows3]
    boot = lambda rows, fn: cluster_bootstrap(rows, fn, draws=DRAWS, seed=SEED)
    out = {'pairs': len(rows3), 'instances': len({r['instance_id'] for r in rows3}),
           'judge_valid': len(judge), 'matcher_ok': len(matcher),
           'matcher_missing': 240 - len(matcher),
           'binary': {'agreement': boot(rows2, lambda rs: sum(r['a'] == r['b'] for r in rs) / len(rs)),
                      'kappa': boot(rows2, kappa)},
           'three_class': {'agreement': boot(rows3, lambda rs: sum(r['a'] == r['b'] for r in rs) / len(rs)),
                           'kappa': boot(rows3, kappa)},
           'matcher_dist': dict(Counter(r['a'] for r in rows3)),
           'judge_dist': dict(Counter(r['b'] for r in rows3))}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, indent=1, sort_keys=True) + '\n')
    def f(d):
        return f"{d['estimate']:.3f} [{d['lo']:.3f}, {d['hi']:.3f}]"
    print(json.dumps({'pairs': out['pairs'], 'instances': out['instances'],
                      'binary_agreement': f(out['binary']['agreement']),
                      'binary_kappa': f(out['binary']['kappa']),
                      'three_agreement': f(out['three_class']['agreement']),
                      'three_kappa': f(out['three_class']['kappa']),
                      'matcher_missing': out['matcher_missing']}, indent=1))


if __name__ == '__main__':
    main()