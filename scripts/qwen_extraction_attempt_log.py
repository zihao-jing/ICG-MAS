"""Attempt log for Qwen-235B extraction in the A2 pilot: cause of each attempt, from results.json. $0.

    ./.conda-env/bin/python -m scripts.qwen_extraction_attempt_log
Output: rebuttal/pilots/20261115_injection_amendA2/qwen_extraction_attempt_log.md
"""
import json
import collections
import scripts.injection_amendA2 as A2
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'rebuttal/pilots/20261115_injection_amendA2/qwen_extraction_attempt_log.md'


def main():
    cases = json.loads((ROOT / 'rebuttal/pilots/20261115_injection_amendA2/results.json').read_text())['cases']
    ext = [c for c in cases if c['type'] == 'extraction' and c['model'] == 'qwen235b']
    pk = A2.pkgs('qwen235b')
    rows, cause = [], collections.Counter()
    for c in ext:
        F = A2.content(c['plan']['fact'])
        pool = {u['unit_id']: u for u in pk[c['instance']]['checkpoints']['extraction']}
        res = (c['check'] or {}).get('residual_units') or []
        cov = max([len(F & A2.content(pool[u]['text'])) / len(F) for u, _ in res if u in pool] or [0.0])
        if c['f1'] >= 1.0:
            k = 'answer unchanged (F1 1.0)'
        elif not res:
            k = 'answer changed, no residue'
        else:
            classes = {f for _, f in res}
            k = 'residue: ' + ('faithful' if 'faithful' in classes else '/'.join(sorted(classes)))
        cause[k] += 1
        rows.append((c['instance'], round(c['f1'], 3), k, len(res), round(cov, 2)))
    lines = ['# Qwen-235B extraction, A2 pilot: attempt log', '',
             f'Attempts: {len(ext)} (cap 120). Kept: {sum(1 for c in ext if c["kept"])}.',
             'Source: `results.json` in this folder; coverage = max token coverage of the anchor fact among residual units (scripts/injection_amendA2).',
             '', '| Cause | Attempts |', '| --- | ---: |']
    for k, v in cause.most_common():
        lines.append(f'| {k} | {v} |')
    lines += ['', '| Instance | F1 | Cause | Residual units | Max coverage of residual units |',
              '| --- | ---: | --- | ---: | ---: |']
    for r in rows:
        lines.append(f'| {r[0]} | {r[1]} | {r[2]} | {r[3]} | {r[4]} |')
    OUT.write_text('\n'.join(lines) + '\n')
    print('\n'.join(lines[:12]))
    print('residue attempts with a residual unit at coverage >= 0.6:',
          sum(1 for r in rows if r[2].startswith('residue') and r[4] >= 0.6))


if __name__ == '__main__':
    main()
