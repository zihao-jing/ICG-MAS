"""Build the E4 distortion (Phase 1b) and aggregation (Phase 2) action rows, including the
author-checked distortion swaps. No model call and no outcome is read.

Every field comes from the frozen case list, the action/donor manifest, the matcher labels, the
trace packages and the returned E4 distortion-swap author check. The donor swap is marked
author-checked only where the returned answer says the span is verbatim; the returned
`swap_preserves_fact` value is carried as `preserves_target`, and a true value flags a donor that is
not a mismatched control. Nothing here writes or changes a label.

    python -m scripts.build_e4_phase23_actions
"""
import json
from pathlib import Path

from src.audit.critical_fact_validation import load_run, reconstruct_states_and_scores
from src.audit.pilot_common import digest, freeze

from scripts.build_e4_manifest import BASE, COHORT, MATCHER, build_cases

GROUPS = {'distortion': ['Rerun', 'R-dist', 'V-dist'],
          'candidate_aggregation': ['Rerun', 'R-agg', 'generic_retry', 'R-agg+']}
CALLS_PER = {'distortion': 5, 'candidate_aggregation': 6}
RETURNS = Path('rebuttal/annotation/packets_20261110/returns/E4_distortion_swap')
PRIVATE = Path('rebuttal/pilots/20261110_packets/E4_swap_private_map.json')
OUT = Path('rebuttal/pilots/20261111_e4_phase23/actions_phase23.json')


def swaps():
    pm = json.loads(PRIVATE.read_text())
    out = {}
    for p in sorted(RETURNS.glob('annotator_*.jsonl')):
        for line in p.read_text().splitlines():
            if not line.strip():
                continue
            r = json.loads(line)
            m = pm[r['item_id']]
            out[(m['instance_id'], m['model'])] = r['answers']
    assert len(out) == 25
    return out


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
    check = swaps()
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
        row = {'trace_id': digest([inst, fam, 1]), 'instance_id': inst, 'benchmark': m['benchmark'],
               'group': g, 'model': BASE[fam], 'n_agents': len(p['source_contexts']),
               'board_units': board, 'pool_units': p['checkpoints']['extraction'],
               'source_contexts': p['source_contexts'], 'question': p['question'],
               'facts': lab['facts'], 'carriers': lab['carriers'],
               'answer_text': p['baseline_prediction'], 'gold_answer': p.get('gold_answer'),
               'answer_aliases': [], 'target_agent': m['target_agent'],
               'donor_agent': m.get('donor_agent'), 'target_unit_ids': m['target_unit_ids'],
               'donor_unit_ids': m.get('donor_unit_ids') or [],
               'board_sha256': m['board_sha256'], 'label_status': 'frozen_manifest',
               'phase23_arms': GROUPS[g]}
        if g == 'distortion':
            ans = check[(inst, fam)]
            ctx = {s['agent_id']: s['text'] for s in p['source_contexts']}
            for key, arm, span in (('target_swap', 'repair', m['target_span']),
                                   ('donor_swap', 'control', m['donor_span'])):
                uid = m[arm]['unit_ids'][0]
                unit = next(u for u in board if u['unit_id'] == uid)
                assert span in ctx[unit['agent_id']], (inst, arm, 'span not verbatim in context')
                row[key] = {'unit_id': uid, 'text': span,
                            'author_checked': ans['swap_is_verbatim'] == 'yes',
                            'verbatim_in_context': True}
            row['donor_swap']['preserves_target'] = ans['swap_preserves_fact'] == 'yes'
            row['swap_preserves_fact'] = ans['swap_preserves_fact']
        assert row['trace_id'] not in seen
        seen.add(row['trace_id'])
        rows.append(row)
    per = {g: sum(r['group'] == g for r in rows) for g in GROUPS}
    runs = sum(len(GROUPS[r['group']]) for r in rows)
    calls = sum(CALLS_PER[r['group']] for r in rows)
    assert per == {'distortion': 25, 'candidate_aggregation': 105}, per
    assert (runs, calls) == (495, 755), (runs, calls)
    assert sum(len(GROUPS[r['group']]) for r in rows if r['group'] == 'distortion') == 75
    assert sum(CALLS_PER[r['group']] for r in rows if r['group'] == 'distortion') == 125
    assert sum(len(GROUPS[r['group']]) for r in rows if r['group'] == 'candidate_aggregation') == 420
    assert sum(CALLS_PER[r['group']] for r in rows if r['group'] == 'candidate_aggregation') == 630
    OUT.parent.mkdir(parents=True, exist_ok=True)
    freeze(OUT, rows)
    print(json.dumps({'rows': len(rows), 'per_group': per, 'runs': runs, 'calls': calls,
                      'arms': sorted({a for r in rows for a in r['phase23_arms']}),
                      'donor_preserves_target': sum(1 for r in rows
                                                     if (r.get('donor_swap') or {}).get('preserves_target')),
                      'actions_sha256': digest(OUT.read_bytes()),
                      'outcome_read': False}, indent=1))


if __name__ == '__main__':
    main()