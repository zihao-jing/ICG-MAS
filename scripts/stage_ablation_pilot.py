"""E3: checkpoint-removal route counts (no model calls).

    ./run.sh python -m scripts.stage_ablation_pilot          # 50-trace pilot
    ./run.sh python -m scripts.stage_ablation_pilot --all    # all traces
"""
import argparse
import hashlib
import json
import math
from collections import defaultdict
from pathlib import Path

from src.audit.stage_ablation import route, route_changes
from src.audit.validation_gate import require

ROOT = Path(__file__).resolve().parent.parent
PREREG = ROOT / 'rebuttal/pilots/prereg/E3-pilot.md'
SRC = ROOT / 'rebuttal/pilots/20261113_main_table_redo/results.json'
N_PILOT = 50
SEED = 43


def sha(obj):
    return hashlib.sha256(json.dumps(obj, sort_keys=True).encode()).hexdigest()


def wilson(k, n):
    if n == 0:
        return (0.0, 0.0)
    z = 1.96
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (max(0.0, c - h), min(1.0, c + h))


def main():
    man = json.loads((ROOT / 'rebuttal/pilots/20261113_main_table_redo/run_manifest.json').read_text())
    require('main_table_carrier_board_musique', man['system_sha256'])
    require('main_table_presence_extraction_musique', man['system_sha256'])
    ap = argparse.ArgumentParser()
    ap.add_argument('--all', action='store_true')
    args = ap.parse_args()
    outdir = ROOT / ('rebuttal/pilots/20261114_e3_full' if args.all
                     else 'rebuttal/pilots/20261114_e3_pilot')
    d = json.loads(SRC.read_text())
    if any('_n' in x['key'].split('|')[1] for x in d['items']):
        require('main_table_carrier_board_silobench', man['system_sha256'])
        require('main_table_presence_extraction_silobench', man['system_sha256'])
    by = defaultdict(dict)
    for x in d['items']:
        model, inst, cp = x['key'].split('|')
        by[(model, inst)][cp] = x
    traces = []
    excluded = 0
    for (model, inst), cps in by.items():
        ext, board = cps['extraction'], cps['board']

        def labels(row):
            if row.get('labeller') is not None:
                return row['labeller']
            if 'facts' not in row:
                return None
            return {f['fact_id']: {'status': 'absent', 'fidelity': 'absent'}
                    for f in row['facts']}

        e, b = labels(ext), labels(board)
        if e is None or b is None:
            excluded += 1
            continue
        assert set(e) == set(b)
        traces.append({'model': model, 'instance': inst,
                       'extraction': e, 'board': b,
                       'answer_correct': bool(board['answer_correct'])})
    traces.sort(key=lambda t: sha(['E3-pilot', SEED, t['model'], t['instance']]))
    pilot = traces if args.all else traces[:N_PILOT]
    full = [route(t['extraction'], t['board'], t['answer_correct']) for t in pilot]
    removals = {
        'pool': ['pool'],
        'fidelity': ['fidelity'],
        'aggregation': ['aggregation'],
        'all_three': ['pool', 'fidelity', 'aggregation'],
    }
    out = {'n': len(pilot), 'excluded_no_facts': excluded,
           'full_route_counts': {}, 'removals': {}, 'by_model': {}}
    for r in set(full):
        out['full_route_counts'][r] = full.count(r)
    for name, rem in removals.items():
        res = route_changes(pilot, rem)
        lo, hi = wilson(res['changed'], res['n'])
        out['removals'][name] = {
            'n': res['n'], 'changed': res['changed'], 'share': res['changed_share'],
            'ci': [lo, hi],
            'pairs': {f'{a}->{b}': v for (a, b), v in sorted(res['pairs'].items())},
        }
        for model in sorted({t['model'] for t in pilot}):
            sub = [t for t in pilot if t['model'] == model]
            rr = route_changes(sub, rem)
            out['by_model'].setdefault(model, {})[name] = {
                'n': rr['n'], 'changed': rr['changed'], 'share': rr['changed_share']}
    outdir.mkdir(parents=True, exist_ok=True)
    pop = [{k: t[k] for k in ('model', 'instance', 'answer_correct')}
           for t in pilot]
    (outdir / 'population.json').write_text(json.dumps(pop, indent=1) + '\n')
    (outdir / 'results.json').write_text(json.dumps(out, indent=1) + '\n')
    ident = {'rule_sha256': hashlib.sha256(PREREG.read_bytes()).hexdigest(),
             'population_sha256': hashlib.sha256(
                 (outdir / 'population.json').read_bytes()).hexdigest(),
             'source_sha256': hashlib.sha256(SRC.read_bytes()).hexdigest(),
             'calls': 0, 'cost_usd': 0.0}
    (outdir / 'run_identity.json').write_text(json.dumps(ident, indent=1) + '\n')
    lines = [('# E3 full: checkpoint-removal route counts' if args.all
              else '# E3 pilot: checkpoint-removal route counts'), '',
             f'Rule `rebuttal/pilots/prereg/E3-pilot.md` (sha256 '
             f'`{ident["rule_sha256"][:12]}`), frozen before the run. '
             f'{len(pilot)} traces ({excluded} no-fact traces excluded from '
             f'{len(traces) + excluded}); 0 model calls, $0.00. Stage: audit '
             'routing checkpoints (extraction pool, board fidelity, '
             'aggregation). Descriptive only.', '',
             '**Labels.** Extraction presence (prompt v3) is validated on '
             'MuSiQue: 60 fresh traces, 176 facts, agreement .915 [.863, .952], '
             'kappa .780 [.665, .877], against a frozen Gemini reference. '
             'Silo-Bench extraction **fails** (30 traces, 250 facts, agreement '
             '.860 [.811, .901], kappa .127 [0, .270]) and this run has no '
             'Silo-Bench traces (all 2,395 are MuSiQue), so no Silo-Bench row '
             'is reported. Board carrier identification is validated at .881 '
             '[.823, .925], MuSiQue, cross-model. Fidelity/distortion labels '
             'remain unvalidated.', '',
             'The presence label **over-credits in all disagreements** '
             '(MuSiQue 15 over-credits, 0 misses; Silo-Bench 35 over-credits, '
             '0 misses). It is lenient, so extraction loss counts are lower '
             'bounds.', '',
             '## Full route', '', '| route | n |', '|---|---:|']
    for r in sorted(out['full_route_counts']):
        lines.append(f'| {r} | {out["full_route_counts"][r]} |')
    lines += ['', '## Routes changed when a check is removed', '',
              '| removed | changed | share [95% CI] | route changes |',
              '|---|---:|---|---|']
    for name, r in out['removals'].items():
        pairs = ', '.join(f'{k} ({v})' for k, v in r['pairs'].items()) or 'none'
        lines.append(f'| {name} | {r["changed"]}/{r["n"]} | '
                     f'{r["share"]:.3f} [{r["ci"][0]:.3f}, {r["ci"][1]:.3f}] | {pairs} |')
    lines += ['', 'The pool row is **definitional**: `route()` assigns '
              '`extraction` exactly when the pool check finds a required fact '
              'absent, so removing the check moves every extraction-routed '
              'trace and no other. The fidelity row is likewise exactly the '
              'traces the fidelity check routes to `distortion`.']
    (outdir / 'report.md').write_text('\n'.join(lines) + '\n')
    print(json.dumps({'n': len(pilot), 'full': out['full_route_counts'],
                      'removals': {k: v['changed'] for k, v in out['removals'].items()}},
                     indent=1))


if __name__ == '__main__':
    main()