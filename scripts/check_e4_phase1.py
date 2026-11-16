"""E4 Phase 1 sanity check (no model call, no contrast).

Same report-only volume rule as the corrected pilot check `scripts/check_e4_pilot.py`
(SHA-256 `c2ce2835…`): a pair outside +/-10% is flagged, never failed. That script expects all ten
arms on every case, which Phase 1 does not run by design, so this one checks the arms each group is
allowed to have.

    python -m scripts.check_e4_phase1
"""
import argparse, json
from pathlib import Path

from src.eval.evaluate import answer_f1
from src.protocols.base import extract_answer

ARMS = {'extraction_omission': ['Rerun', 'R-ext', 'V-ext'],
        'selection_omission': ['Rerun', 'R-sel', 'V-sel'],
        'correct_control': ['Rerun'],
        'partial': ['Rerun']}
PAIRS = {'extraction_omission': [('R-ext', 'V-ext')],
         'selection_omission': [('R-sel', 'V-sel')],
         'correct_control': [], 'partial': []}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--output', default='rebuttal/results/batch1/E4_phase1')
    ap.add_argument('--actions', default='rebuttal/pilots/20261110_e4_phase1/actions_phase1.json')
    a = ap.parse_args()
    files = sorted((Path(a.output) / 'raw').glob('*.json'))
    cases = [json.loads(p.read_text()) for p in files]
    man = {r['trace_id']: r for r in json.loads(Path(a.actions).read_text())}
    missing, empty = [], []
    fmt = {'fidelity_calls': 0, 'fidelity_not_ok': 0}
    pairs = {'checked': 0, 'matched': 0, 'flagged_over_10pct': []}
    rerun = {'checked': 0, 'status_match': 0}
    forbidden = set()
    for case in cases:
        known = [r for r in case if r.get('arm')]
        if not known:
            missing.append(f"{case[0].get('trace_id')}:whole case failed")
            continue
        g = known[0]['group']
        by = {r['arm']: r for r in case}
        missing += [f"{known[0]['trace_id']}:{arm}" for arm in ARMS[g] if arm not in by]
        empty += [f"{known[0]['trace_id']}:{arm}" for arm in ARMS[g]
                  if arm in by and not (by[arm].get('answer') or '').strip()]
        forbidden |= set(by) - set(ARMS[g])
        for arm in by:
            if by[arm].get('fidelity') is not None:
                fmt['fidelity_calls'] += 1
                fmt['fidelity_not_ok'] += by[arm]['fidelity'].get('status') != 'ok'
        for rep, ctl in PAIRS[g]:
            if rep not in by or ctl not in by:
                continue
            m = by[rep].get('control_match') or {}
            pairs['checked'] += 1
            pairs['matched'] += bool(m.get('matched'))
            if m.get('repair_tokens'):
                ratio = abs(m['repair_tokens'] - m.get('control_tokens', 0)) / m['repair_tokens']
                if ratio > 0.10:
                    pairs['flagged_over_10pct'].append(f"{known[0]['trace_id']}:{rep}/{ctl}")
        if 'Rerun' in by and known[0]['trace_id'] in man:
            m = man[known[0]['trace_id']]
            gold = {'answer': m['gold_answer'], 'answer_aliases': m.get('answer_aliases', [])}
            base_ok = answer_f1(extract_answer(m['answer_text']), gold) >= 1.0
            rerun_ok = answer_f1(extract_answer(by['Rerun']['answer']), gold) >= 1.0
            rerun['checked'] += 1
            rerun['status_match'] += base_ok == rerun_ok
    out = {'cases': len(cases), 'missing_arms': missing, 'empty_answers': empty,
           'forbidden_arms': sorted(forbidden),
           'format_failure_rate': {'fidelity_calls': fmt['fidelity_calls'],
                                   'not_ok': fmt['fidelity_not_ok'],
                                   'rate': round(fmt['fidelity_not_ok'] / fmt['fidelity_calls'], 4)
                                   if fmt['fidelity_calls'] else None},
           'volume_controls': {'checked': pairs['checked'], 'matched': pairs['matched'],
                               'flagged_over_10pct': pairs['flagged_over_10pct']},
           'rerun_status': rerun, 'contrast_computed': False}
    print(json.dumps(out, indent=1))
    assert not missing and not empty, 'Phase 1 is missing an arm or an answer'
    assert not forbidden, 'an arm outside the Phase 1 set was run'
    # Pairs outside +/-10% are flagged, not failed (E4-v7.md:18; experiment_plan.md:307).


if __name__ == '__main__':
    main()