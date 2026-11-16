"""Judge alone on the 89-case set, from stored outputs (no calls).

Gemini judge: rebuttal/pilots/20261113_attribution_comparison/results_v2.json (field judge.stage).
Qwen judge:   rebuttal/pilots/20261115_b5_attribution_2x2/judge_qwen.json (field stage).
Output: rebuttal/pilots/20261116_stage_naming/judge89_score.json
"""
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
P = ROOT / 'rebuttal/pilots'
OUT = P / '20261116_stage_naming'


def wilson(k, n, z=1.959964):
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return [round(max(0, c - h), 3), round(min(1, c + h), 3)]


def main():
    gem = {i['key']: i for i in json.loads((P / '20261113_attribution_comparison/results_v2.json').read_text())['items']}
    qwen = {i['key']: i for i in json.loads((P / '20261115_b5_attribution_2x2/judge_qwen.json').read_text())['items']}
    cases = json.loads((P / '20261113_attribution_comparison/cases_v2.json').read_text())
    keys = [c['key'] for c in cases]
    known = {c['key']: c['known_stage'] for c in cases}
    pop = {c['key']: c['population'] for c in cases}
    beyond = [k for k in keys if pop[k] == 'cohort']
    res = {'n_cases': len(keys), 'populations': {p: sum(1 for k in keys if pop[k] == p) for p in set(pop.values())}}
    for name, src, get in (('gemini', gem, lambda i: (i.get('judge') or {}).get('stage')),
                           ('qwen', qwen, lambda i: i.get('stage'))):
        ok = [k for k in keys if get(src[k]) == known[k]]
        res[name] = {'k': len(ok), 'n': len(keys), 'rate': round(len(ok) / len(keys), 3),
                     'wilson95': wilson(len(ok), len(keys)),
                     'correct_injected': sum(1 for k in ok if pop[k] == 'injected'),
                     'correct_cohort': sum(1 for k in ok if pop[k] == 'cohort')}
    res['cases_beyond_82_cohort'] = len(beyond)
    res['note'] = 'The 82 known-cause runs = 30 injected cases + 11 deleted-fact cases; the 89 = 30 injected + 59 cohort. The 59 cohort cases are not in the 82, so naming (A2, A3) cannot be scored on them.'
    (OUT / 'judge89_score.json').write_text(json.dumps(res, indent=1))
    print(json.dumps(res, indent=1))


if __name__ == '__main__':
    main()
