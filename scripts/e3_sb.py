"""E3 Silo-Bench routes at $0, exploratory (labels not validated for SB)."""
import json
import math
from collections import Counter, defaultdict
from pathlib import Path

from src.audit.stage_ablation import route, route_changes

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / 'rebuttal/pilots/20261113_sb_presence_full/results.json'
OUT = ROOT / 'rebuttal/pilots/20261114_e3_sb'


def wilson(k, n):
    z = 1.96; p = k / n; d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return max(0.0, c - h), min(1.0, c + h)


def main():
    items = json.loads(SRC.read_text())['items']
    g = defaultdict(dict)
    for x in items:
        if x['model'] == 'qwen235b':
            g[x['instance_id']][x['checkpoint']] = x
    traces = [{'instance': i, 'extraction': v['extraction']['labeller'],
               'board': v['board']['labeller'],
               'answer_correct': bool(v['board']['answer_correct'])}
              for i, v in g.items() if 'extraction' in v and 'board' in v and isinstance(v['extraction'].get('labeller'), dict) and isinstance(v['board'].get('labeller'), dict)]
    full = [route(t['extraction'], t['board'], t['answer_correct']) for t in traces]
    counts = Counter(full)
    removals = {'pool': ['pool'], 'fidelity': ['fidelity'],
                'aggregation': ['aggregation'],
                'all_three': ['pool', 'fidelity', 'aggregation']}
    out = {'n': len(traces), 'routes': dict(counts), 'removals': {}}
    for name, rem in removals.items():
        r = route_changes(traces, rem)
        lo, hi = wilson(r['changed'], r['n'])
        out['removals'][name] = {'n': r['n'], 'changed': r['changed'],
                                 'share': r['changed_share'], 'ci': [lo, hi],
                                 'pairs': {f'{a}->{b}': v for (a, b), v in sorted(r['pairs'].items())}}
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / 'population.json').write_text(json.dumps(
        [{k: t[k] for k in ('instance', 'answer_correct')} for t in traces], indent=1) + '\n')
    (OUT / 'results.json').write_text(json.dumps(out, indent=1) + '\n')
    lines = ['# E3 Silo-Bench routes (exploratory)', '',
             f'{len(traces)} Silo-Bench qwen235b traces, random_relay, k = 3 labels from '
             '`20261113_sb_presence_full`; $0, no model calls.', '',
             '**Exploratory.** The Silo-Bench extraction presence label is unvalidated '
             '(prompt v3 failed at kappa .127; fixed prompt v4 also failed at kappa .553, '
             'cluster CI [0.000, 1.000]). The board carrier label is unvalidated for '
             'Silo-Bench, fidelity/distortion is unvalidated, and these labels are '
             'random_relay, not the score-ranked relay of the MuSiQue E3 run. No row here '
             'is a validated correction.', '',
             '| route | n |', '|---|---:|']
    for r in sorted(counts):
        lines.append(f'| {r} | {counts[r]} |')
    lines += ['', '| removed | changed | share [95% CI] |', '|---|---:|---|']
    for name, r in out['removals'].items():
        lines.append(f"| {name} | {r['changed']}/{r['n']} | "
                     f"{r['share']:.3f} [{r['ci'][0]:.3f}, {r['ci'][1]:.3f}] |")
    (OUT / 'report.md').write_text('\n'.join(lines) + '\n')
    print(json.dumps({'n': len(traces), 'routes': dict(counts),
                      'removals': {k: v['changed'] for k, v in out['removals'].items()}}))


if __name__ == '__main__':
    main()