"""E4 distortion (Phase 1b) and aggregation (Phase 2): component-targeted runs under the frozen
E4-v7 design and the author-checked swap gate. One attempt per ledger record; failed calls are
logged, left unscored and not retried. Stops at `--max-calls` (config cap) or the cost cap.

    python -m scripts.run_e4_phase23 --config rebuttal/pilots/configs/E4-phase1b.json          # dry
    python -m scripts.run_e4_phase23 --config rebuttal/pilots/configs/E4-phase1b.json --execute
"""
import argparse, datetime, hashlib, json
from pathlib import Path

from src.audit.base_tokenizers import volume_match
from src.audit.matcher_v2 import CARRIER_PROMPT, carrier_schema, structured_call
from src.audit.pilot_common import CallLedger, digest, freeze
from src.audit.repair_study import _strong_repair_analysis_request, _strong_repair_final_request
from src.audit.semantic_matcher import validate_carriers

from scripts.pilot_e1 import messages
from scripts.run_frozen_repair import original_prompt

ALLOWED = {'Rerun', 'R-dist', 'V-dist', 'R-agg', 'R-agg+', 'generic_retry'}
PARTS = {'distortion': {'distortion': ['Rerun', 'R-dist', 'V-dist']},
         'aggregation': {'candidate_aggregation': ['Rerun', 'R-agg', 'generic_retry', 'R-agg+']}}


def utc():
    return datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def run_case(row, cfg, ledger):
    out, swapped = [], {}
    model, key, original = row['model'], row['trace_id'], row['board_units']
    for arm in row['phase23_arms']:
        assert arm in ALLOWED, arm
        board = [dict(u) for u in original]
        token_units, no_op = [], False
        if arm in ('R-dist', 'V-dist'):
            swap = row['target_swap'] if arm == 'R-dist' else row['donor_swap']
            if not swap.get('author_checked'):
                raise ValueError('Unverified distortion swap')
            no_op = not any(u['agent_id'] == row['target_agent' if arm == 'R-dist' else 'donor_agent']
                            for u in board)
            if not no_op:
                matches = [u for u in board if u['unit_id'] == swap['unit_id']]
                if len(matches) != 1:
                    raise ValueError('Missing swap unit')
                matches[0]['text'] = swap['text']
                token_units = [dict(matches[0])]
        if no_op:
            answer = out[0]['answer']
        elif arm in ('R-agg', 'generic_retry'):
            audited = arm == 'R-agg'
            req = _strong_repair_analysis_request(row, board, audited=audited, model=model,
                                                  max_tokens=2048, condition=arm)
            work = ledger.call(key + '/' + arm + '/ledger', model,
                               messages(req.system_query, req.user_query))
            req = _strong_repair_final_request(row, board, work, audited=audited, model=model,
                                               max_tokens=4096, condition=arm)
            answer = ledger.call(key + '/' + arm + '/answer', model,
                                 messages(req.system_query, req.user_query), max_tokens=4096)
        else:
            sys, user = original_prompt(row, board)
            answer = ledger.call(key + '/' + arm + '/answer',
                                 cfg['strong_model'] if arm == 'R-agg+' else model,
                                 messages(sys, user), max_tokens=4096)
        fidelity = None
        if arm in ('R-dist', 'V-dist') and not no_op:
            match_input = {'question': row['question'], 'facts': row['facts'],
                           'source_contexts': row['source_contexts'],
                           'extraction': row['pool_units'], 'board': board}
            t = {'checkpoints': {'extraction': row['pool_units'], 'board': board}}
            fidelity = structured_call(ledger, key + '/' + arm + '/fidelity',
                                       cfg['judge_model'], CARRIER_PROMPT, match_input,
                                       carrier_schema(row['facts'], t),
                                       lambda x: validate_carriers(x, row['facts'], t))
        out.append({'trace_id': key, 'arm': arm, 'answer': answer,
                    'board_sha256': digest(board), 'no_op': no_op,
                    'token_units': token_units, 'fidelity': fidelity,
                    'label_status': 'frozen_manifest'})
        if arm in ('R-dist', 'V-dist'):
            swapped[arm] = out[-1]
    if 'R-dist' in swapped and 'V-dist' in swapped:
        r, c = swapped['R-dist'], swapped['V-dist']
        match = volume_match(model, r['token_units'], c['token_units'])
        match['matched'] = match['matched'] and r['no_op'] == c['no_op']
        r['control_match'] = c['control_match'] = match
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--config')
    ap.add_argument('--execute', action='store_true')
    ap.add_argument('--max-calls', type=int)
    a = ap.parse_args()
    cfg = json.loads(Path(a.config).read_text())
    rows = json.loads(Path(cfg['action_manifest']).read_text())
    assert sha(cfg['action_manifest']) == cfg['manifest_sha256'], 'action manifest changed'
    assert sha(cfg['prereg']) == cfg['prereg_sha256'], 'preregistration changed'
    assert sha(cfg['cohort']) == cfg['cohort_sha256'], 'cohort changed'
    part = cfg['part']
    keep = {g for g in PARTS[part]}
    rows = [r for r in rows if r['group'] in keep]
    for r in rows:
        assert r['phase23_arms'] == PARTS[part][r['group']]
        if r['group'] == 'distortion':
            assert r['donor_swap']['author_checked'], 'donor swap not author-checked'
            assert r['target_swap']['author_checked']
    runs = sum(len(r['phase23_arms']) for r in rows)
    calls = sum({'distortion': 5, 'candidate_aggregation': 6}[r['group']] for r in rows)
    print(json.dumps({'part': part, 'rows': len(rows), 'runs': runs, 'planned_calls': calls,
                      'groups': {g: sum(r['group'] == g for r in rows) for g in keep},
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
        for row in rows:
            try:
                recs = run_case(row, cfg, ledger)
            except Exception as exc:
                recs = [{'trace_id': row['trace_id'], 'group': row['group'], 'arm': None,
                         'failed': True, 'error': type(exc).__name__ + ': ' + str(exc)}]
            freeze(out / 'raw' / f"{digest(row['trace_id'])}.json", recs)
            done.append({'trace_id': row['trace_id'], 'group': row['group'],
                         'arms': [x['arm'] for x in recs]})
            print(json.dumps({'done': row['instance_id'], 'group': row['group'],
                              'calls': len(ledger.done), 'cost_usd': round(spent(), 6)}), flush=True)
            if spent() > cfg['cost_cap_usd']:
                raise RuntimeError('cost cap reached; stop')
    finally:
        ledger.close()
    failed = sum(1 for x in ledger.done.values() if not x.get('success'))
    summary = {'part': part, 'rows': len(rows), 'rows_completed': len(done),
               'runs_planned': runs, 'runs_completed': sum(len(d['arms']) for d in done),
               'calls': len(ledger.done), 'failed_calls': failed,
               'cost_usd': round(spent(), 6), 'cost_cap_usd': cfg['cost_cap_usd'],
               'max_calls': cap,
               'per_group': {g: sum(d['group'] == g for d in done) for g in keep},
               'arms_executed': sorted({x for d in done for x in d['arms'] if x}),
               'contrast_computed': False, 'outcome_read': False, 'end_utc': utc()}
    (out / 'summary.json').write_text(json.dumps(summary, indent=1, sort_keys=True) + '\n')
    print(json.dumps(summary, indent=1), flush=True)


if __name__ == '__main__':
    main()