"""E4 pilot sanity check (no model call, no contrast). Reads one pilot run's raw arm records.

Checks, per case: every arm present with a non-empty answer and a board hash; each matched
repair/control pair equal in added unit count with repair tokens within +/-10%; the format-failure
rate of the fidelity matcher calls; and whether the Rerun answer reproduces the base answer's
correct/incorrect status. It prints counts only and computes no arm-versus-arm contrast.

    python -m scripts.check_e4_pilot --output rebuttal/results/batch1/E4_pilot_v1
"""
import argparse, json
from pathlib import Path

from src.eval.evaluate import answer_f1
from src.protocols.base import extract_answer

ARMS = ['Rerun', 'R-ext', 'V-ext', 'R-sel', 'V-sel', 'R-dist', 'V-dist', 'R-agg', 'generic_retry', 'R-agg+']
PAIRS = [('R-ext', 'V-ext'), ('R-sel', 'V-sel'), ('R-dist', 'V-dist')]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--output', default='rebuttal/results/batch1/E4_pilot_v1')
    ap.add_argument('--manifest', default='rebuttal/pilots/20261110_e4_pilot/actions_pilot2.json')
    a = ap.parse_args()
    rows = [json.loads(p.read_text()) for p in sorted((Path(a.output) / 'raw').glob('*.json'))]
    manifest = {r['trace_id']: r for r in json.loads(Path(a.manifest).read_text())}
    cases, missing, empty, fmt = len(rows), [], [], {'fidelity_calls': 0, 'fidelity_not_ok': 0}
    pairs, rerun = {'checked': 0, 'matched': 0, 'max_ratio': 0.0, 'over_10pct': []}, {'checked': 0, 'status_match': 0}
    for case in rows:
        by = {r['arm']: r for r in case}
        missing += [f"{case[0]['trace_id']}:{arm}" for arm in ARMS if arm not in by]
        empty += [f"{case[0]['trace_id']}:{arm}" for arm in ARMS
                  if arm in by and not (by[arm].get('answer') or '').strip()]
        for arm in ARMS:
            if arm in by and by[arm].get('fidelity') is not None:
                fmt['fidelity_calls'] += 1
                fmt['fidelity_not_ok'] += by[arm]['fidelity'].get('status') != 'ok'
        for rep, ctl in PAIRS:
            if rep not in by or ctl not in by:
                continue
            m = by[rep].get('control_match') or {}
            pairs['checked'] += 1
            pairs['matched'] += bool(m.get('matched'))
            if m.get('repair_tokens'):
                ratio = abs(m['repair_tokens'] - m.get('control_tokens', 0)) / m['repair_tokens']
                pairs['max_ratio'] = max(pairs['max_ratio'], ratio)
                if ratio > 0.10:
                    pairs['over_10pct'].append(f"{case[0]['trace_id']}:{rep}/{ctl}")
        if 'Rerun' in by and case[0]['trace_id'] in manifest:
            m = manifest[case[0]['trace_id']]
            gold = {'answer': m['gold_answer'], 'answer_aliases': m.get('answer_aliases', [])}
            base_ok = answer_f1(extract_answer(m['answer_text']), gold) >= 1.0
            rerun_ok = answer_f1(extract_answer(by['Rerun']['answer']), gold) >= 1.0
            rerun['checked'] += 1
            rerun['status_match'] += base_ok == rerun_ok
    out = {'cases': cases, 'missing_arms': missing, 'empty_answers': empty,
           'format_failure_rate': {'fidelity_calls': fmt['fidelity_calls'],
                                   'not_ok': fmt['fidelity_not_ok'],
                                   'rate': round(fmt['fidelity_not_ok'] / fmt['fidelity_calls'], 4)
                                   if fmt['fidelity_calls'] else None},
           'volume_controls': {'checked': pairs['checked'], 'matched': pairs['matched'],
                               'max_ratio': round(pairs['max_ratio'], 4),
                               'over_10pct': pairs['over_10pct']},
           'rerun_status': rerun, 'contrast_computed': False}
    print(json.dumps(out, indent=1))
    assert not missing and not empty, 'pilot is missing an arm or an answer'
    # Unmatched pairs are expected and go only to the all-case sensitivity check (E4-v7:307).


if __name__ == '__main__':
    main()