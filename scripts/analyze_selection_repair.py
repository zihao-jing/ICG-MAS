"""Analyze the selection-repair control: exact match, paired contrasts, cluster CIs.

    ./run.sh python -m scripts.analyze_selection_repair
"""
import json
import random
from pathlib import Path

from src.eval.evaluate import answer_f1
from src.protocols.base import extract_answer

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'rebuttal/pilots/20261114_selection_repair_full'
MAN = ROOT / 'rebuttal/pilots/20261114_selection_repair/actions.json'
SEED = 42
DRAWS = 2000


def exact(ans, gold):
    return answer_f1(extract_answer(ans or ''), gold) >= 1.0


def f1(ans, gold):
    return answer_f1(extract_answer(ans or ''), gold)


def ci(vals, groups):
    """Cluster bootstrap over instance groups for the mean of vals."""
    if not vals:
        return [None, None]
    rng = random.Random(SEED)
    keys = sorted(groups)
    out = []
    for _ in range(DRAWS):
        pick = [keys[rng.randrange(len(keys))] for _ in keys]
        sample = [v for k in pick for v in groups[k]]
        out.append(sum(sample) / len(sample))
    out.sort()
    return [out[int(.025 * DRAWS)], out[int(.975 * DRAWS)]]


def main():
    man = {r['trace_id']: r for r in json.loads(MAN.read_text())}
    raw = [json.loads(p.read_text()) for p in sorted((OUT / 'raw').glob('*.json'))]
    cases = []
    for recs in raw:
        if not recs or not recs[0].get('arm'):
            continue
        by = {r['arm']: r for r in recs}
        m = man[recs[0]['trace_id']]
        gold = {'answer': m['gold_answer'], 'answer_aliases': m.get('answer_aliases', [])}
        case = {'trace_id': recs[0]['trace_id'], 'instance_id': m['instance_id'],
                'correct': {a: exact(by[a].get('answer'), gold) for a in ('Rerun', 'R-sel', 'V-sel')},
                'f1': {a: f1(by[a].get('answer'), gold) for a in ('Rerun', 'R-sel', 'V-sel')},
                'matched': bool((by['R-sel'].get('control_match') or {}).get('matched'))}
        cases.append(case)

    def summary(subset, name):
        groups = {}
        for c in subset:
            for a in ('Rerun', 'R-sel', 'V-sel'):
                groups.setdefault((c['instance_id'], a), []).append(float(c['correct'][a]))
        res = {'name': name, 'n': len(subset),
               'exact': {a: round(sum(c['correct'][a] for c in subset) / len(subset), 3)
                         for a in ('Rerun', 'R-sel', 'V-sel')},
               'f1': {a: round(sum(c['f1'][a] for c in subset) / len(subset), 3)
                      for a in ('Rerun', 'R-sel', 'V-sel')},
               'volume_matched': sum(c['matched'] for c in subset)}
        for rep, ctl in (('R-sel', 'Rerun'), ('R-sel', 'V-sel'), ('V-sel', 'Rerun')):
            diffs = [c['correct'][rep] - c['correct'][ctl] for c in subset]
            g = {}
            for c, d in zip(subset, diffs):
                g.setdefault(c['instance_id'], []).append(float(d))
            res[f'{rep}_minus_{ctl}'] = {
                'mean': round(sum(diffs) / len(diffs), 4),
                'ci': [round(x, 4) if x is not None else None for x in ci(diffs, g)],
                'improved': sum(1 for d in diffs if d > 0),
                'worsened': sum(1 for d in diffs if d < 0),
                'unchanged': sum(1 for d in diffs if d == 0)}
        return res

    out = {'n_cases': len(cases), 'all': summary(cases, 'all'),
           'wrong_at_rerun': summary([c for c in cases if not c['correct']['Rerun']],
                                     'wrong at Rerun'),
           'volume_matched': summary([c for c in cases if c['matched']],
                                      'volume matched (R-sel/V-sel within 10%)'),
           'volume_flagged': summary([c for c in cases if not c['matched']],
                                      'volume flagged (>10%)'),
           'cost_usd': json.loads((OUT / 'summary.json').read_text())['cost_usd'],
           'note': 'exact match / F1 against MuSiQue gold; cluster bootstrap over '
                   'instances, 2,000 draws, seed 42; 4 of 56 selection traces are '
                   'unrepairable and excluded; 38 of 52 R-sel/V-sel pairs exceed the '
                   '10% token-volume band and are reported separately'}
    (OUT / 'analysis.json').write_text(json.dumps(out, indent=1) + '\n')
    print(json.dumps(out, indent=1))


if __name__ == '__main__':
    main()