"""E4 Phase 1: component-targeted runs for extraction, selection, controls and partial only.

No distortion arm, no aggregation arm, no contrast. One attempt per ledger record; a failed call is
logged, left unscored, and not retried. Stops at `--max-calls` (cap in the config) or the cost cap.

    python -m scripts.run_e4_phase1 --config rebuttal/pilots/configs/E4-phase1.json          # dry
    python -m scripts.run_e4_phase1 --config rebuttal/pilots/configs/E4-phase1.json --execute
"""
import argparse, datetime, hashlib, json
from pathlib import Path

from src.audit.base_tokenizers import volume_match
from src.audit.matcher_v2 import CARRIER_PROMPT, carrier_schema, structured_call
from src.audit.pilot_common import CallLedger, digest, freeze
from src.audit.semantic_matcher import validate_carriers
from src.protocols.relay import _EXTRACTION_SYSTEM, _build_extraction_prompt, _parse_units

from scripts.pilot_e1 import messages
from scripts.run_frozen_repair import original_prompt

ALLOWED = {'Rerun', 'R-ext', 'V-ext', 'R-sel', 'V-sel'}


def utc():
    return datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def run_case_arms(row, cfg, ledger, arms):
    out, new_units = [], {}
    model, key, original = row['model'], row['trace_id'], row['board_units']
    for arm in arms:
        assert arm in ALLOWED, arm
        board = [dict(u) for u in original]
        added, token_units, no_op = [], [], False
        if arm in ('R-ext', 'V-ext'):
            agent = row['target_agent'] if arm == 'R-ext' else row['donor_agent']
            context = next(s['text'] for s in row['source_contexts'] if s['agent_id'] == agent)
            raw = ledger.call(key + '/' + arm + '/extract', model,
                              messages(_EXTRACTION_SYSTEM,
                                       _build_extraction_prompt(context, row['question'], cfg['max_units'])))
            texts = _parse_units(raw, cfg['max_units'])
            if arm == 'V-ext':
                texts = texts[:len(new_units['R-ext'])]
            added = [{'unit_id': f'{arm}:{j}', 'agent_id': agent, 'text': s} for j, s in enumerate(texts)]
            board += added
            new_units[arm] = added
        elif arm in ('R-sel', 'V-sel'):
            ids = row['target_next_unit_ids'] if arm == 'R-sel' else row['donor_next_unit_ids'][:len(new_units['R-sel'])]
            agent = row['target_agent'] if arm == 'R-sel' else row['donor_agent']
            no_op = not any(u['agent_id'] == agent for u in original)
            if not no_op:
                added = [next(u for u in row['pool_units'] if u['unit_id'] == i) for i in ids[:2]]
                board += added
            new_units[arm] = added
        if no_op:
            answer = out[0]['answer']
        else:
            system, user = original_prompt(row, board)
            answer = ledger.call(key + '/' + arm + '/answer', model,
                                 messages(system, user), max_tokens=cfg['max_tokens'])
        fidelity = None
        if arm in ('R-ext', 'V-ext') and not no_op:
            match_input = {'question': row['question'], 'facts': row['facts'],
                           'source_contexts': row['source_contexts'],
                           'extraction': row['pool_units'], 'board': board}
            t = {'checkpoints': {'extraction': row['pool_units'], 'board': board}}
            fidelity = structured_call(ledger, key + '/' + arm + '/fidelity', cfg['judge_model'],
                                       CARRIER_PROMPT, match_input,
                                       carrier_schema(row['facts'], t),
                                       lambda x: validate_carriers(x, row['facts'], t))
        out.append({'trace_id': key, 'group': row['group'], 'arm': arm, 'answer': answer,
                    'board_sha256': digest(board), 'no_op': no_op, 'added_units': added,
                    'token_units': token_units or added, 'fidelity': fidelity,
                    'label_status': row['label_status']})
    by_arm = {r['arm']: r for r in out}
    if 'R-ext' in by_arm and 'V-ext' in by_arm:
        r, c = by_arm['R-ext'], by_arm['V-ext']
        m = volume_match(model, r['token_units'], c['token_units'])
        m['matched'] = m['matched'] and r['no_op'] == c['no_op']
        r['control_match'] = c['control_match'] = m
    if 'R-sel' in by_arm and 'V-sel' in by_arm:
        r, c = by_arm['R-sel'], by_arm['V-sel']
        m = volume_match(model, r['token_units'], c['token_units'])
        m['matched'] = m['matched'] and r['no_op'] == c['no_op']
        r['control_match'] = c['control_match'] = m
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--config', default='rebuttal/pilots/configs/E4-phase1.json')
    ap.add_argument('--execute', action='store_true')
    ap.add_argument('--max-calls', type=int)
    a = ap.parse_args()
    cfg = json.loads(Path(a.config).read_text())
    rows = json.loads(Path(cfg['action_manifest']).read_text())
    assert sha(cfg['action_manifest']) == cfg['manifest_sha256'], 'action manifest changed'
    assert sha(cfg['prereg']) == cfg['prereg_sha256'], 'preregistration changed'
    assert sha(cfg['runner']) == cfg['runner_sha256'], 'runner changed'
    assert sha(cfg['sanity_check']) == cfg['sanity_check_sha256'], 'sanity check changed'
    assert sha(cfg['phase1_check']) == cfg['phase1_check_sha256'], 'phase 1 check changed'
    runs = sum(len(r['phase1_arms']) for r in rows)
    calls = sum({'extraction_omission': 7, 'selection_omission': 3}.get(r['group'], 1) for r in rows)
    assert not any(set(r['phase1_arms']) - ALLOWED for r in rows)
    print(json.dumps({'rows': len(rows), 'runs': runs, 'planned_calls': calls,
                      'groups': {g: sum(r['group'] == g for r in rows) for g in
                                 ('extraction_omission', 'selection_omission', 'correct_control', 'partial')},
                      'arms': sorted({x for r in rows for x in r['phase1_arms']}),
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
                recs = run_case_arms(row, cfg, ledger, row['phase1_arms'])
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
    summary = {'rows': len(rows), 'rows_completed': len(done),
               'runs_planned': runs, 'runs_completed': sum(len(d['arms']) for d in done),
               'calls': len(ledger.done), 'failed_calls': failed,
               'cost_usd': round(spent(), 6), 'cost_cap_usd': cfg['cost_cap_usd'],
               'max_calls': cap, 'per_group': {g: sum(d['group'] == g for d in done) for g in
                                               ('extraction_omission', 'selection_omission',
                                                'correct_control', 'partial')},
               'arms_executed': sorted({x for d in done for x in d['arms'] if x}),
               'forbidden_arms_executed': sorted({x for d in done for x in d['arms']
                                                  if x} - ALLOWED),
               'contrast_computed': False, 'outcome_read': False, 'end_utc': utc()}
    (out / 'summary.json').write_text(json.dumps(summary, indent=1, sort_keys=True) + '\n')
    print(json.dumps(summary, indent=1), flush=True)


if __name__ == '__main__':
    main()