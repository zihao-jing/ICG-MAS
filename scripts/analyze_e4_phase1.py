"""Pre-registered E4 Phase 1 analysis (E4-v7 amendment A1). Outcomes are read here for the first time.

Per group and benchmark: n cases, repair-minus-Rerun deltas, the matched-pair repair-minus-volume-
control contrast (matched pairs only), and the all-case volume-adjusted sensitivity fitted per
benchmark. Descriptive when fewer than 10 instances or fewer than 5 matched pairs. No distortion or
aggregation arm exists in the inputs.

    python -m scripts.analyze_e4_phase1
"""
import json
from collections import defaultdict
from pathlib import Path

from src.audit.e4_balance import matched_volume_contrast, volume_sensitivity
from src.audit.pilot_common import cluster_bootstrap
from src.eval.evaluate import answer_f1
from src.protocols.base import extract_answer

OUT = Path('rebuttal/results/batch1/E4_phase1')
ACTIONS = Path('rebuttal/pilots/20261110_e4_phase1/actions_phase1.json')
GROUPS = ['extraction_omission', 'selection_omission', 'correct_control', 'partial']
DRAWS, SEED = 2000, 42


def score(answer, gold):
    return 1.0 if answer and answer_f1(extract_answer(answer), gold) >= 1.0 else 0.0


def mean_ci(rows):
    stat = lambda rs: sum(r['delta'] for r in rs) / len(rs) if rs else None
    return cluster_bootstrap(rows, stat, draws=DRAWS, seed=SEED)


def contrast_rows(rs):
    return [{'instance_id': c['instance_id'], 'failure_type': c['group'],
             'protocol': c['protocol'], 'benchmark': c['benchmark'], 'base_model': c['model'],
             'repair_arm': c['repair_arm'], 'repair_tokens': c['repair_tokens'],
             'control_tokens': c['control_tokens'], 'repair_score': c['repair_score'],
             'control_score': c['control_score'], 'matched': c['matched']} for c in rs]


def main():
    actions = {r['trace_id']: r for r in json.loads(ACTIONS.read_text())}
    cases = []
    for p in sorted((OUT / 'raw').glob('*.json')):
        recs = [r for r in json.loads(p.read_text()) if r.get('arm')]
        if not recs:
            continue
        tid = recs[0]['trace_id']
        a = actions[tid]
        gold = {'answer': a['gold_answer'], 'answer_aliases': a.get('answer_aliases', [])}
        by = {r['arm']: r for r in recs}
        row = {'trace_id': tid, 'instance_id': a['instance_id'], 'model': a['model'],
               'group': a['group'], 'protocol': a['benchmark'],
               'benchmark': 'MuSiQue' if a['benchmark'] == 'MQ' else 'Silo-Bench',
               'scores': {arm: score(by[arm]['answer'], gold) for arm in by},
               'base_ok': score(a['answer_text'], gold)}
        arm = 'R-ext' if a['group'] == 'extraction_omission' else (
            'R-sel' if a['group'] == 'selection_omission' else None)
        if arm:
            cm = by[arm].get('control_match') or {}
            ctl = 'V-ext' if arm == 'R-ext' else 'V-sel'
            row.update(matched=bool(cm.get('matched')), repair_arm=arm, control_arm=ctl,
                       repair_tokens=cm.get('repair_tokens'), control_tokens=cm.get('control_tokens'),
                       repair_score=row['scores'][arm], control_score=row['scores'][ctl])
        cases.append(row)

    out = {'cases': len(cases), 'groups': {}, 'caveats': {}, 'draws': DRAWS, 'seed': SEED}
    for g in GROUPS:
        rs = [c for c in cases if c['group'] == g]
        d = {'n_cases': len(rs), 'n_clusters': len({c['instance_id'] for c in rs}),
             'deltas_vs_rerun': {}, 'cells': {}}
        arm = 'R-ext' if g == 'extraction_omission' else 'R-sel' if g == 'selection_omission' else None
        if arm is None:
            d['rerun_accuracy'] = {'estimate': sum(c['scores']['Rerun'] for c in rs) / len(rs),
                                   'n': len(rs)}
        else:
            for a in (arm, 'V-ext' if arm == 'R-ext' else 'V-sel'):
                rows = [{'instance_id': c['instance_id'],
                         'delta': c['scores'][a] - c['scores']['Rerun']} for c in rs]
                d['deltas_vs_rerun'][a] = mean_ci(rows)
            for b in ('MQ', 'SB-5', 'SB-10'):
                prs = [c for c in rs if c['protocol'] == b]
                cell = {'n_cases': len(prs), 'n_clusters': len({c['instance_id'] for c in prs}),
                        'matched_pairs': sum(c['matched'] for c in prs)}
                if cell['matched_pairs']:
                    cell['matched_contrast'] = matched_volume_contrast(
                        contrast_rows([c for c in prs if c['matched']]), draws=DRAWS, seed=SEED)
                else:
                    cell['matched_contrast'] = {'pairs': 0, 'possible_pairs': len(prs), 'clusters': 0,
                                                'estimate': None, 'status': 'no matched pairs'}
                cell['sensitivity'] = (volume_sensitivity(contrast_rows(prs), draws=DRAWS, seed=SEED)
                                       if prs else {'status': 'no pairs', 'clusters': 0})
                d['cells'][b] = cell
        out['groups'][g] = d

    paired = [c for c in cases if 'matched' in c]
    fmt = defaultdict(lambda: {'calls': 0, 'not_ok': 0, 'cases_not_ok': []})
    for p in sorted((OUT / 'raw').glob('*.json')):
        for r in json.loads(p.read_text()):
            if r.get('arm') and r.get('fidelity') is not None:
                f = fmt[r['group']]
                f['calls'] += 1
                if r['fidelity'].get('status') != 'ok':
                    f['not_ok'] += 1
                    f['cases_not_ok'].append({'trace_id': r['trace_id'], 'arm': r['arm']})
    mism = [c for c in cases if c['scores']['Rerun'] != c['base_ok']]
    cohort = json.loads(Path('rebuttal/results/batch1/E4_pool_matcher/E4_cohort_frozen.json').read_text())
    out['caveats'] = {
        'volume_flagged': sum(not c['matched'] for c in paired),
        'volume_matched': sum(c['matched'] for c in paired),
        'volume_pairs': len(paired),
        'volume_flagged_list': [{'instance': c['instance_id'], 'protocol': c['protocol'],
                                 'repair': c['repair_arm']} for c in paired if not c['matched']],
        'fidelity': dict(fmt),
        'rerun_status_mismatch': [{'instance': c['instance_id'], 'model': c['model'],
                                   'group': c['group'], 'base': c['base_ok'],
                                   'rerun': c['scores']['Rerun']} for c in mism],
        'matcher_failed_cases': sum(c['matcher_status'] != 'ok' for c in cohort['case']),
        'a1_vs_realized': ('A1 enumerated every frozen donor candidate (36 extraction donor volumes over '
                           '17 cases); the run realized one donor per case: 17 extraction pairs, '
                           f"{sum(c['group'] == 'extraction_omission' and c['matched'] for c in cases)} "
                           'matched, and 1 selection pair, 0 matched.')}
    (OUT / 'analysis.json').write_text(json.dumps(out, indent=1, sort_keys=True) + '\n')

    # table source rows (T05, T06), same numbers as above
    labels = {'extraction_omission': 'extraction omission', 'selection_omission': 'selection omission'}
    main_rows, vol_rows = [], []
    for c in cases:
        if c['group'] not in labels:
            continue
        for arm in ('R-ext', 'V-ext', 'R-sel', 'V-sel'):
            if arm in c['scores']:
                main_rows.append({'row': f"{labels[c['group']]} ({c['protocol']})", 'col': arm,
                                  'cluster': c['instance_id'],
                                  'delta': c['scores'][arm] - c['scores']['Rerun']})
        if c.get('matched'):
            vol_rows.append({'row': f"{labels[c['group']]} ({c['protocol']})",
                             'col': f"{c['repair_arm']} minus {c['control_arm']}",
                             'cluster': c['instance_id'],
                             'delta': c['repair_score'] - c['control_score'], 'n_pairs': 1})
    # a Silo-Bench cell with zero matched pairs still gets a row, so T06 can show the
    # pre-registered "no same-volume control available" reading and the zero count
    sb = {}
    for c in cases:
        if c['group'] not in labels or not c['protocol'].startswith('SB-'):
            continue
        key = (labels[c['group']], c['protocol'])
        cell = sb.setdefault(key, {'arm': c['repair_arm'], 'ctl': c['control_arm'],
                                   'cluster': c['instance_id'], 'matched': 0})
        cell['matched'] += bool(c['matched'])
    for (label, proto), cell in sb.items():
        if cell['matched'] == 0:
            vol_rows.append({'row': f"{label} ({proto})",
                             'col': f"{cell['arm']} minus {cell['ctl']}",
                             'cluster': cell['cluster'], 'delta': None, 'n_pairs': 0})
    td = Path('rebuttal/results/batch1/E4')
    td.mkdir(parents=True, exist_ok=True)
    for name, rows in (('main_delta_rows.jsonl', main_rows),
                       ('volume_control_delta_rows.jsonl', vol_rows)):
        (td / name).write_text(''.join(json.dumps(r) + '\n' for r in rows))
    print(json.dumps(out, indent=1))


if __name__ == '__main__':
    main()