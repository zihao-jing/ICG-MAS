"""Frozen E4 analysis for the distortion (Phase 1b) and aggregation (Phase 2) arms (E4-v7).

Outcomes are read here for the first time. Reads only the frozen action rows and the two raw
output directories. No call, no label written.

Distortion: R-dist vs V-dist on natural matched pairs (equal added units, base tokens within
±10%), deltas vs Rerun, and the author swap-check counts. Silo-Bench cells with fewer than 5
matched pairs read "no same-volume control available" (A2); N<10 instances is descriptive.
Aggregation: R-agg vs generic_retry paired by construction (same two-call structure), deltas vs
Rerun for every arm, exact McNemar on the discordant pairs.

    python -m scripts.analyze_e4_phase23
"""
import json, math
from collections import Counter
from pathlib import Path

from src.audit.e4_balance import matched_volume_contrast
from src.audit.pilot_common import cluster_bootstrap
from src.eval.evaluate import answer_f1
from src.protocols.base import extract_answer

ACTIONS = Path('rebuttal/pilots/20261111_e4_phase23/actions_phase23.json')
P1B = Path('rebuttal/results/batch1/E4_phase1b')
P2 = Path('rebuttal/results/batch1/E4_phase2')
OUT = Path('rebuttal/results/batch1/E4_phase23')
TABLES = Path('rebuttal/results/batch1/E4')
DRAWS, SEED = 2000, 42
BMS = ('MQ', 'SB-5', 'SB-10')


def score(answer, gold):
    return 1.0 if answer and answer_f1(extract_answer(answer), gold) >= 1.0 else 0.0


def mean_ci(rows):
    if not rows:
        return {'estimate': None, 'lo': None, 'hi': None, 'valid_draws': 0, 'clusters': 0}
    stat = lambda rs: sum(r['delta'] for r in rs) / len(rs) if rs else None
    res = cluster_bootstrap(rows, stat, draws=DRAWS, seed=SEED)
    return res


def mcnemar(a, b):
    """Two-sided exact McNemar on paired binary scores a vs b."""
    disc = [(x, y) for x, y in zip(a, b) if x != y]
    n1 = sum(1 for x, y in disc if x > y)
    n0 = len(disc) - n1
    n = n1 + n0
    if n == 0:
        return {'b': 0, 'c': 0, 'p': 1.0}
    k = min(n1, n0)
    tail = sum(math.comb(n, i) for i in range(k + 1)) / 2 ** n
    return {'b': n1, 'c': n0, 'p': min(1.0, 2 * tail)}


def load_raw(d, actions):
    cases = []
    for p in sorted(d.glob('raw/*.json')):
        recs = json.loads(p.read_text())
        recs = [r for r in recs if r.get('arm')]
        if not recs:
            continue
        tid = recs[0]['trace_id']
        a = actions[tid]
        gold = {'answer': a['gold_answer'], 'answer_aliases': a.get('answer_aliases') or []}
        by = {r['arm']: r for r in recs}
        case = {'trace_id': tid, 'instance_id': a['instance_id'], 'model': a['model'],
                'benchmark': a['benchmark'], 'group': a['group'],
                'scores': {arm: score(by[arm]['answer'], gold) for arm in by},
                'answers': {arm: by[arm]['answer'] for arm in by},
                'base_ok': score(a['answer_text'], gold),
                'token_units': {arm: by[arm].get('token_units') for arm in by},
                'fidelity': {arm: by[arm].get('fidelity') for arm in by},
                'no_op': {arm: by[arm].get('no_op') for arm in by}}
        if 'R-dist' in by and by['R-dist'].get('control_match'):
            cm = by['R-dist']['control_match']
            case['matched'] = bool(cm.get('matched'))
            case['repair_tokens'] = cm.get('repair_tokens')
            case['control_tokens'] = cm.get('control_tokens')
        cases.append(case)
    return cases


def cells(cases, arm, ctl=None):
    out = {}
    for b in BMS:
        rs = [c for c in cases if c['benchmark'] == b]
        cell = {'n_cases': len(rs), 'n_clusters': len({c['instance_id'] for c in rs}),
                'deltas_vs_rerun': {}, 'descriptive_only': len({c['instance_id'] for c in rs}) < 10}
        for a in sorted({a for c in rs for a in c['scores'] if a != 'Rerun'}):
            cell['deltas_vs_rerun'][a] = mean_ci(
                [{'instance_id': c['instance_id'], 'delta': c['scores'][a] - c['scores']['Rerun']}
                 for c in rs])
        if ctl:
            paired = [c for c in rs if arm in c['scores'] and ctl in c['scores']]
            if arm == 'R-dist':
                mp = [c for c in paired if c.get('matched')]
                cell['matched_pairs'] = len(mp)
                if len(mp) < 5:
                    cell['matched_contrast'] = {'pairs': len(mp), 'possible_pairs': len(paired),
                                                'status': 'no same-volume control available'}
                else:
                    cell['matched_contrast'] = matched_volume_contrast(
                        [{'instance_id': c['instance_id'], 'benchmark': b,
                          'matched': True, 'repair_score': c['scores']['R-dist'],
                          'control_score': c['scores']['V-dist']} for c in mp],
                        draws=DRAWS, seed=SEED)
            cell['paired_contrast'] = mean_ci(
                [{'instance_id': c['instance_id'], 'delta': c['scores'][arm] - c['scores'][ctl]}
                 for c in paired])
            cell['mcnemar'] = mcnemar([c['scores'][arm] for c in paired],
                                      [c['scores'][ctl] for c in paired])
        out[b] = cell
    tail = [c for c in cases if c['benchmark'] == 'all']
    return out


def main():
    actions = {r['trace_id']: r for r in json.loads(ACTIONS.read_text())}
    dist = load_raw(P1B, actions)
    agg = load_raw(P2, actions)
    assert len(dist) == 25, len(dist)
    assert len(agg) == 105, len(agg)

    out = {'draws': DRAWS, 'seed': SEED, 'distortion': {}, 'aggregation': {}}
    out['distortion'] = {
        'cases': len(dist), 'instances': len({c['instance_id'] for c in dist}),
        'arms': sorted({a for c in dist for a in c['scores']}),
        'by_benchmark': cells(dist, 'R-dist', 'V-dist'),
        'all': cells(dist, 'R-dist', 'V-dist')['MQ'],
        'author_swap': {'target_checked': sum(1 for r in dist if actions[r['trace_id']]['target_swap']['author_checked']),
                        'donor_checked': sum(1 for r in dist if actions[r['trace_id']]['donor_swap']['author_checked']),
                        'donor_preserves_target': sum(1 for r in dist if actions[r['trace_id']]['donor_swap'].get('preserves_target'))},
        'no_ops': sum(1 for c in dist if c['no_op'].get('R-dist') or c['no_op'].get('V-dist')),
        'fidelity': {a: {'calls': sum(1 for c in dist if c['fidelity'].get(a) is not None),
                         'not_ok': sum(1 for c in dist
                                       if (c['fidelity'].get(a) or {}).get('status') not in (None, 'ok'))}
                     for a in ('R-dist', 'V-dist')},
        'rerun_status_mismatch': [{'instance': c['instance_id'], 'model': c['model'],
                                   'base': c['base_ok'], 'rerun': c['scores']['Rerun']}
                                  for c in dist if c['scores']['Rerun'] != c['base_ok']],
    }
    # pooled across benchmarks (distortion is 23 MQ / 1 SB-5 / 1 SB-10)
    pooled = []
    for c in dist:
        if c.get('matched') is not None:
            pooled.append({'instance_id': c['instance_id'], 'delta':
                           c['scores']['R-dist'] - c['scores']['V-dist'], 'matched': c['matched']})
    out['distortion']['matched_all_benchmarks'] = {
        'pairs': sum(r['matched'] for r in pooled), 'possible': len(pooled),
        'estimate': (sum(c['scores']['R-dist'] - c['scores']['V-dist'] for c in dist) /
                     len(dist))}
    out['distortion']['deltas_all_cases'] = {
        a: mean_ci([{'instance_id': c['instance_id'], 'delta': c['scores'][a] - c['scores']['Rerun']}
                    for c in dist]) for a in ('R-dist', 'V-dist')}

    out['aggregation'] = {
        'cases': len(agg), 'instances': len({c['instance_id'] for c in agg}),
        'arms': sorted({a for c in agg for a in c['scores']}),
        'by_benchmark': cells(agg, 'R-agg', 'generic_retry'),
        'deltas_all_cases': {a: mean_ci([{'instance_id': c['instance_id'],
                                          'delta': c['scores'][a] - c['scores']['Rerun']}
                                         for c in agg]) for a in ('R-agg', 'generic_retry', 'R-agg+')},
        'rerun_status_mismatch': [{'instance': c['instance_id'], 'model': c['model'],
                                   'base': c['base_ok'], 'rerun': c['scores']['Rerun']}
                                  for c in agg if c['scores']['Rerun'] != c['base_ok']],
        'mcnemar_all': mcnemar([c['scores']['R-agg'] for c in agg],
                               [c['scores']['generic_retry'] for c in agg]),
    }

    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / 'analysis.json').write_text(json.dumps(out, indent=1, sort_keys=True) + '\n')
    fmt = lambda d: 'NA' if not d or d.get('estimate') is None else (
        f"{d['estimate']:.3f} [{d.get('lo'):.3f}, {d.get('hi'):.3f}]" if d.get('lo') is not None
        else f"{d['estimate']:.3f} (no CI)")
    L = ['# E4 Phase 1b (distortion) and Phase 2 (aggregation): frozen analysis', '',
         'Read from raw outputs only; 95% CIs are percentile instance-cluster bootstrap, '
         f'{DRAWS} draws, seed {SEED}. N<10 clusters descriptive.', '']
    L += ['## Distortion (25 cases)', '']
    for b, v in out['distortion']['by_benchmark'].items():
        L += [f"- **{b}**: {v['n_cases']} cases/{v['n_clusters']} instances; R-dist−Rerun "
              f"{fmt(v['deltas_vs_rerun']['R-dist'])}; V-dist−Rerun {fmt(v['deltas_vs_rerun']['V-dist'])}; "
              f"matched pairs {v.get('matched_pairs', 0)} → "
              f"{v['matched_contrast'].get('status', fmt(v['matched_contrast']))}; "
              f"paired R-dist−V-dist {fmt(v['paired_contrast'])}; McNemar p={v['mcnemar']['p']:.3f}"]
    L += ['', f"Author swap checks: target {out['distortion']['author_swap']['target_checked']}/25, "
          f"donor {out['distortion']['author_swap']['donor_checked']}/25; donors that preserve the "
          f"target fact {out['distortion']['author_swap']['donor_preserves_target']}/25.", '']
    L += ['## Aggregation (105 cases)', '']
    for b, v in out['aggregation']['by_benchmark'].items():
        L += [f"- **{b}**: {v['n_cases']} cases/{v['n_clusters']} instances; R-agg−Rerun "
              f"{fmt(v['deltas_vs_rerun']['R-agg'])}; generic_retry−Rerun "
              f"{fmt(v['deltas_vs_rerun']['generic_retry'])}; R-agg−generic_retry "
              f"{fmt(v['paired_contrast'])}; McNemar p={v['mcnemar']['p']:.3f}; R-agg+−Rerun "
              f"{fmt(v['deltas_vs_rerun']['R-agg+'])}"]
    L += ['', f"All-case McNemar (R-agg vs generic_retry): p={out['aggregation']['mcnemar_all']['p']:.3f} "
          f"({out['aggregation']['mcnemar_all']['b']} R-agg-only vs "
          f"{out['aggregation']['mcnemar_all']['c']} generic-only)."]
    L += ['']
    (OUT / 'analysis.md').write_text('\n'.join(L) + '\n')
    print(json.dumps(out, indent=1, sort_keys=True))


if __name__ == '__main__':
    main()