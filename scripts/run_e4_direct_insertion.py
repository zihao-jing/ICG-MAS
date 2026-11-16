"""E4 direct insertion (amendment A3): append the frozen targeted fact, re-aggregate, and a
volume-matched donor control. 17 extraction cases, 2 arms, 34 planned calls.

One attempt per ledger record; a failed call is logged, unscored and not retried. Stops at
`--max-calls` (cap 34) or the $0.10 cost cap. No distortion arm, no aggregation arm, no contrast.

    python -m scripts.run_e4_direct_insertion --config rebuttal/pilots/configs/E4-direct-insertion.json
    python -m scripts.run_e4_direct_insertion --config ... --execute
"""
import argparse
import datetime
import hashlib
import json
from pathlib import Path

from src.audit.base_tokenizers import volume_match
from src.audit.pilot_common import CallLedger, digest, freeze

from scripts.pilot_e1 import messages
from scripts.run_frozen_repair import original_prompt

ALLOWED = {'R-ins', 'V-ins'}


def utc():
    return datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def norm(s):
    return ' '.join(''.join(ch if ch.isalnum() else ' ' for ch in s.casefold()).split())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--config', default='rebuttal/pilots/configs/E4-direct-insertion.json')
    ap.add_argument('--execute', action='store_true')
    ap.add_argument('--max-calls', type=int)
    a = ap.parse_args()
    cfg = json.loads(Path(a.config).read_text())
    assert sha(cfg['plan']) == cfg['plan_sha256'], 'insertion plan changed'
    assert sha(cfg['prereg']) == cfg['prereg_sha256'], 'amendment changed'
    assert sha(cfg['actions']) == cfg['actions_sha256'], 'action manifest changed'
    assert sha(cfg['runner']) == cfg['runner_sha256'], 'runner changed'
    plan = json.loads(Path(cfg['plan']).read_text())
    cases = plan['cases']
    assert len(cases) == 17
    rows = {r['trace_id']: r for r in json.loads(Path(cfg['actions']).read_text())
            if r['group'] == 'extraction_omission'}
    calls = 2 * len(cases)
    print(json.dumps({'cases': len(cases), 'runs': 2 * len(cases), 'planned_calls': calls,
                      'max_calls': a.max_calls or cfg['max_calls'],
                      'cost_cap_usd': cfg['cost_cap_usd'], 'execute': a.execute,
                      'start_utc': utc()}), flush=True)
    if not a.execute:
        return
    cap = a.max_calls or cfg['max_calls']
    assert cap <= cfg['max_calls']
    out = Path(cfg['output'])
    ledger = CallLedger(out, cfg, cfg['prereg'], cap)
    spent = lambda: sum((x.get('cost_usd') or 0) for x in ledger.done.values())
    done = []
    try:
        for case in cases:
            row = rows[case['trace_id']]
            recs = []
            for arm, unit in (('R-ins', case['repair_unit']), ('V-ins', case['control_unit'])):
                if unit is None:
                    recs.append({'trace_id': case['trace_id'], 'arm': arm, 'failed': True,
                                 'error': 'control cannot be matched'})
                    continue
                board = [dict(u) for u in row['board_units']] + [dict(unit)]
                system, user = original_prompt(row, board)
                check = norm(unit['text']) in norm(user)
                if not check:
                    recs.append({'trace_id': case['trace_id'], 'arm': arm, 'failed': True,
                                 'error': 'manipulation check failed before dispatch'})
                    continue
                try:
                    answer = ledger.call(case['trace_id'] + '/' + arm + '/answer', case['model'],
                                         messages(system, user), max_tokens=cfg['max_tokens'])
                except Exception as exc:
                    recs.append({'trace_id': case['trace_id'], 'group': 'extraction_omission',
                                 'arm': arm, 'failed': True, 'manipulation_check': check,
                                 'error': type(exc).__name__ + ': ' + str(exc)})
                    break
                recs.append({'trace_id': case['trace_id'], 'group': 'extraction_omission',
                             'arm': arm, 'answer': answer, 'manipulation_check': check,
                             'inserted_unit': unit, 'board_sha256': digest(board), 'no_op': False})
            by = {r['arm']: r for r in recs if r.get('arm')}
            if 'R-ins' in by and 'V-ins' in by:
                m = volume_match(case['model'], [case['repair_unit']], [case['control_unit']])
                m['matched'] = m['matched'] and by['R-ins'].get('manipulation_check') is True \
                    and by['V-ins'].get('manipulation_check') is True
                by['R-ins']['control_match'] = by['V-ins']['control_match'] = m
            freeze(out / 'raw' / f"{digest(case['trace_id'])}.json", recs)
            done.append({'trace_id': case['trace_id'], 'instance_id': case['instance_id'],
                         'arms': [r['arm'] for r in recs if r.get('arm')]})
            print(json.dumps({'done': case['instance_id'], 'calls': len(ledger.done),
                              'cost_usd': round(spent(), 6)}), flush=True)
            if spent() > cfg['cost_cap_usd']:
                raise RuntimeError('cost cap reached; stop')
    finally:
        ledger.close()
    failed = sum(1 for x in ledger.done.values() if not x.get('success'))
    summary = {'cases': len(cases), 'cases_completed': len(done), 'runs_planned': 2 * len(cases),
               'runs_done': sum(len(d['arms']) for d in done), 'calls': len(ledger.done),
               'failed_calls': failed, 'cost_usd': round(spent(), 6),
               'cost_cap_usd': cfg['cost_cap_usd'], 'max_calls': cap,
               'arms_executed': sorted({x for d in done for x in d['arms']}),
               'forbidden_arms_executed': sorted({x for d in done for x in d['arms']} - ALLOWED),
               'plan_sha256': cfg['plan_sha256'], 'prereg_sha256': cfg['prereg_sha256'],
               'contrast_computed': False, 'outcome_read': False, 'end_utc': utc()}
    (out / 'summary.json').write_text(json.dumps(summary, indent=1, sort_keys=True) + '\n')
    print(json.dumps(summary, indent=1), flush=True)


if __name__ == '__main__':
    main()