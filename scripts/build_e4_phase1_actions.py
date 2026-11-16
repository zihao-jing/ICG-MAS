"""Build the E4 Phase 1 action rows from the frozen inputs: no model call, no outcome.

Phase 1 covers four groups only: extraction omission (Rerun, R-ext, V-ext), selection omission
(Rerun, R-sel, V-sel), correct controls (Rerun) and partial (Rerun). Distortion and aggregation are
not built here. Every field comes from the frozen case list, the frozen action/donor manifest, the
frozen matcher labels and the trace packages; the board hash is checked against the manifest.

    python -m scripts.build_e4_phase1_actions
"""
import json
from pathlib import Path

from src.audit.critical_fact_validation import load_run, reconstruct_states_and_scores
from src.audit.pilot_common import digest

from scripts.build_e4_manifest import BASE, COHORT, MATCHER, build_cases, next_units

GROUPS = {'extraction_omission': ['Rerun', 'R-ext', 'V-ext'],
          'selection_omission': ['Rerun', 'R-sel', 'V-sel'],
          'correct_control': ['Rerun'],
          'partial': ['Rerun']}
CALLS_PER = {'extraction_omission': 7, 'selection_omission': 3, 'correct_control': 1, 'partial': 1}
OUT = Path('rebuttal/pilots/20261110_e4_phase1/actions_phase1.json')


def main():
    cohort = json.loads(COHORT.read_text())
    ids = {c['instance'] for c in cohort['case']}
    cases, pk = build_cases(ids)
    man = {(r['instance'], r['model']): r for r in cases}
    labels = {}
    for p in MATCHER.glob('*.json'):
        r = json.loads(p.read_text())
        labels[(r['instance_id'], r['model'])] = r
    scores = {}
    for (model, inst), p in pk.items():
        _, responses = load_run(Path(p['run_dir']))
        _, sc = reconstruct_states_and_scores(responses)
        scores[(model, inst)] = sc.get(inst, {})
    rows, seen = [], set()
    for c in cohort['case']:
        m = man[(c['instance'], c['model'])]
        g = m.get('group')
        if m.get('matcher_status') != 'ok' or g not in GROUPS:
            continue
        inst, fam = c['instance'], c['model']
        p = pk[(fam, inst)]
        board = p['checkpoints']['board']
        assert digest(board) == m['board_sha256'], 'board changed since the freeze'
        lab = labels[(inst, fam)]
        rep = m.get('repair') or {}
        ctl = m.get('control') or {}
        target_next = [u['unit_id'] for u in next_units(inst, m['target_agent'], p['checkpoints']['extraction'],
                                                        board, scores[(fam, inst)])]
        donor_next = ([u['unit_id'] for u in next_units(inst, m['donor_agent'], p['checkpoints']['extraction'],
                                                        board, scores[(fam, inst)])]
                      if m.get('donor_agent') is not None else [])
        if g == 'selection_omission':
            assert target_next == rep['unit_ids'], (target_next, rep['unit_ids'])
            assert donor_next == ctl['unit_ids'], (donor_next, ctl['unit_ids'])
        row = {'trace_id': digest([inst, fam, 1]), 'instance_id': inst, 'benchmark': m['benchmark'],
               'group': g, 'model': BASE[fam], 'n_agents': len(p['source_contexts']),
               'board_units': board, 'pool_units': p['checkpoints']['extraction'],
               'source_contexts': p['source_contexts'], 'question': p['question'],
               'facts': lab['facts'], 'carriers': lab['carriers'],
               'answer_text': p['baseline_prediction'], 'gold_answer': p.get('gold_answer'),
               'answer_aliases': [], 'target_agent': m['target_agent'],
               'donor_agent': m.get('donor_agent'), 'target_unit_ids': m['target_unit_ids'],
               'donor_unit_ids': m.get('donor_unit_ids') or [],
               'target_next_unit_ids': target_next, 'donor_next_unit_ids': donor_next,
               'board_sha256': m['board_sha256'], 'label_status': 'frozen_manifest',
               'phase1_arms': GROUPS[g]}
        assert row['trace_id'] not in seen
        seen.add(row['trace_id'])
        rows.append(row)
    assert not any(r['group'] in ('distortion', 'candidate_aggregation') for r in rows)
    per = {g: sum(r['group'] == g for r in rows) for g in GROUPS}
    runs = sum(len(GROUPS[r['group']]) for r in rows)
    calls = sum(CALLS_PER[r['group']] for r in rows)
    assert per == {'extraction_omission': 17, 'selection_omission': 1,
                   'correct_control': 56, 'partial': 15}, per
    assert (runs, calls) == (125, 193), (runs, calls)
    from src.audit.pilot_common import freeze
    freeze(OUT, rows)
    print(json.dumps({'rows': len(rows), 'per_group': per, 'runs': runs, 'calls': calls,
                      'arms': sorted({a for r in rows for a in r['phase1_arms']}),
                      'actions_sha256': digest(OUT.read_bytes()), 'outcome_read': False}, indent=1))


if __name__ == '__main__':
    main()