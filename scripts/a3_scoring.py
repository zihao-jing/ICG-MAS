"""Score the kept A3 + A4 injection cases: audit (word-overlap and statement rules), judge, [R1]; Qwen and Gemini. $0.

    ./.conda-env/bin/python -m scripts.a3_scoring
Output: rebuttal/pilots/20261115_a3_scoring/{score.json,report.md}. Known stage = injected type (extraction or sharding).
A cell is correct when its stage equals the injected type; a missing output (None) counts as wrong.
"""
import json
import math
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
A3 = ROOT / 'rebuttal/pilots/20261115_injection_amendA3/results.json'
A4 = ROOT / 'rebuttal/pilots/20261115_injection_amendA4/results.json'
OUT = ROOT / 'rebuttal/pilots/20261115_a3_scoring'
CELLS = ['audit_qwen_old', 'audit_qwen_fix', 'audit_gemini_old', 'audit_gemini_fix',
         'judge_qwen', 'judge_gemini', 'r1_qwen', 'r1_gemini']
MODELS = ['gemma31b', 'gpt4omini', 'qwen235b']


def wilson(k, n, z=1.96):
    if n == 0:
        return None
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return [round(max(0.0, c - h), 3), round(min(1.0, c + h), 3)]


def load_kept():
    cases = []
    for path, tag in ((A3, 'A3'), (A4, 'A4')):
        if path.exists():
            for c in json.loads(path.read_text())['cases']:
                c['_src'] = tag
                cases.append(c)
    return cases


def main(drop=(), out_dir=None):
    global OUT
    if out_dir:
        OUT = ROOT / out_dir
    cases = load_kept()
    kept = [c for c in cases if c.get('kept') and c['instance'] not in drop]
    out = {'sources': {'A3': str(A3.relative_to(ROOT)), 'A4': str(A4.relative_to(ROOT))},
           'tried': {t: {m: sum(1 for c in cases if c['type'] == t and c['model'] == m) for m in MODELS}
                     for t in ('extraction', 'sharding')},
           'kept': {t: {m: sum(1 for c in kept if c['type'] == t and c['model'] == m) for m in MODELS}
                    for t in ('extraction', 'sharding')},
           'kept_total': {t: sum(1 for c in kept if c['type'] == t) for t in ('extraction', 'sharding')},
           'cells': {}}
    for t in ('extraction', 'sharding'):
        for cell in CELLS:
            for m in MODELS + ['all']:
                sub = [c for c in kept if c['type'] == t and (m == 'all' or c['model'] == m)]
                ok = sum(1 for c in sub if c['methods'].get(cell) == t)
                out['cells'][f'{t}|{cell}|{m}'] = {'k': ok, 'n': len(sub), 'rate': round(ok / len(sub), 3) if sub else None,
                                                   'wilson95': wilson(ok, len(sub))}
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / 'score.json').write_text(json.dumps(out, indent=1))
    lines = ['# A3 + A4 injection: kept cases and scorings', '',
             '2026-11-15. $0, no model calls. Script `scripts/a3_scoring.py`; numbers in `score.json` (same folder). '
             'Sources: `rebuttal/pilots/20261115_injection_amendA3/results.json` and `..._amendA4/results.json`. '
             'Raw counts only (correct of kept cases, n); no rates or intervals. A cell is correct when its stage equals the injected type. '
             'Rule hashes: A3 `Injection-v1-amendment-A3.md` sha256 2fea3ca5…; A4 `Injection-v1-amendment-A4.md` sha256 10e16f8e…. '
             f'Eight scorings: audit (word-overlap and statement rules) on Qwen and Gemini, judge on Qwen and Gemini, [R1] on Qwen and Gemini = {len(CELLS)} cells.', '',
             '## Tried and kept (per type and model)', '',
             '| type | ' + ' | '.join(f'{m} tried / kept' for m in MODELS) + ' | total kept |',
             '| --- | ' + ' | '.join('---' for _ in MODELS) + ' | ---: |']
    for t in ('extraction', 'sharding'):
        lines.append(f'| {t} | ' + ' | '.join(f"{out['tried'][t][m]} / {out['kept'][t][m]}" for m in MODELS)
                     + f" | {out['kept_total'][t]} |")
    lines += ['', '## Scorings (correct of kept cases, n)', '',
              '| type | cell | ' + ' | '.join(MODELS) + ' | all |', '| --- | --- | ' + ' | '.join('---' for _ in MODELS + ['all']) + ' |']
    for t in ('extraction', 'sharding'):
        for cell in CELLS:
            row = []
            for m in MODELS + ['all']:
                v = out['cells'][f'{t}|{cell}|{m}']
                row.append('n/a' if v['n'] == 0 else f"{v['k']} of {v['n']}")
            lines.append(f'| {t} | {cell} | ' + ' | '.join(row) + ' |')
    (OUT / 'report.md').write_text('\n'.join(lines) + '\n')
    print('\n'.join(lines))


if __name__ == '__main__':
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument('--drop', nargs='*', default=[], help='instance ids to exclude from scoring')
    ap.add_argument('--out', default=None, help='output folder under the repo root')
    a = ap.parse_args()
    main(drop=set(a.drop), out_dir=a.out)
