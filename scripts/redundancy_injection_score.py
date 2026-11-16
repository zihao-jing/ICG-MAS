"""Score the redundancy injection run (v1). $0. Reads results.json only.

    ./.conda-env/bin/python -m scripts.redundancy_injection_score
Output: rebuttal/pilots/20261115_redundancy_injection/score.json
"""
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'rebuttal/pilots/20261115_redundancy_injection'


def wilson(k, n, z=1.96):
    if n == 0:
        return None
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return [round(max(0.0, c - h), 3), round(min(1.0, c + h), 3)]


def main():
    res = json.loads((OUT / 'results.json').read_text())['cases']
    arms = ['base/score_ranked', 'duplicated/score_ranked', 'base/redundancy_aware', 'duplicated/redundancy_aware']
    out = {'cases': len(res), 'by_model': {}, 'arms': {}, 'paired': {}, 'verification': {}}
    for m in sorted({r['model'] for r in res}):
        out['by_model'][m] = sum(1 for r in res if r['model'] == m)
    for a in arms:
        f1 = [r['arms'][a]['f1'] for r in res]
        exact = sum(1 for x in f1 if x >= 1.0)
        lex = sum(1 for r in res if r['arms'][a]['gold_string_in_board'])
        out['arms'][a] = {'n': len(f1), 'mean_f1': round(sum(f1) / len(f1), 3) if f1 else None,
                          'exact_f1_1': exact, 'exact_wilson95': wilson(exact, len(f1)),
                          'gold_in_board_lexical': lex, 'gold_in_board_wilson95': wilson(lex, len(f1))}
    for proto in ('score_ranked', 'redundancy_aware'):
        pairs = [(r['arms'][f'base/{proto}']['f1'], r['arms'][f'duplicated/{proto}']['f1']) for r in res]
        drop = sum(1 for b, d in pairs if d < b)
        rise = sum(1 for b, d in pairs if d > b)
        stay = len(pairs) - drop - rise
        out['paired'][proto] = {'duplicated_minus_base_mean': round(sum(d - b for b, d in pairs) / len(pairs), 3),
                                'drop': drop, 'rise': rise, 'unchanged': stay}
    out['verification'] = {
        'duplicate_selected_score_ranked_dup_condition': sum(
            1 for r in res if r['arms']['duplicated/score_ranked']['duplicate_selected']),
        'duplicate_selected_redundancy_aware_dup_condition': sum(
            1 for r in res if r['arms']['duplicated/redundancy_aware']['duplicate_selected']),
        'duplicate_selected_base_condition': sum(
            1 for r in res for p in ('score_ranked', 'redundancy_aware')
            if r['arms'][f'base/{p}']['duplicate_selected'])}
    (OUT / 'score.json').write_text(json.dumps(out, indent=1))
    print(json.dumps(out, indent=1))


if __name__ == '__main__':
    main()
