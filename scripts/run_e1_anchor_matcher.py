"""Single frozen matcher run on the 90 anchor traces (30 instances x 3 base models).

Frozen `semantic-dev-v2` exactly as it ran on dev: no prompt, threshold or setting is changed.
The run config adds only the frozen flag, the anchor ID source and the output path.

One run. Every attempt is logged by CallLedger (append-only intent before dispatch). A transport
failure is caught per trace, the failed call stays in the ledger, the trace is recorded as
`failed` and is NOT retried and NOT scored. The run stops early if more than 5 traces fail.

Run:
  python -m scripts.run_e1_anchor_matcher                 # dry check, no calls
  python -m scripts.run_e1_anchor_matcher --execute --max-calls 540
"""
import argparse, datetime, hashlib, json, sys
from pathlib import Path

from src.audit.matcher_v2 import match_trace, PROMPT_SHA256, VERSION
from src.audit.pilot_common import CallLedger, digest, freeze
from src.audit.semantic_matcher import diagnose

CFG_PATH = Path('rebuttal/pilots/configs/E1-anchor-matcher-frozen.json')
ANC = Path('rebuttal/pilots/20261108_review7/e1_anchor_locked_manifest.json')
DEV_CFG = Path('rebuttal/pilots/configs/E1-v2.json')
MAX_FAILED = 5


def utc():
    return datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def anchor_ids():
    a = json.loads(ANC.read_text())
    ids = [i for v in a['strata'].values() for i in v['ids']]
    assert len(ids) == len(set(ids)) == 30, (len(ids), len(set(ids)))
    return ids


def adapt(trace):
    """Restore the dev trace schema on the anchor packages: the dev traces carried `unit_id` on gold
    supports and source contexts; the anchor packages carry `support_id` / `context_id`. Only these
    opaque handle fields are added. Checkpoints, texts and every other field pass through unchanged.
    The matcher code, prompts and settings are not touched."""
    t = json.loads(json.dumps(trace))
    for u in t['source_supports']:
        u.setdefault('unit_id', 'gold:' + u['support_id'])
    for u in t['source_contexts']:
        u.setdefault('unit_id', 'source:' + u['context_id'])
    assert all(u.get('unit_id') for u in t['source_supports'] + t['source_contexts'])
    return t


def e1_call(diag):
    if diag == 'uncertain':
        return 'exclude_uncertain'
    if diag == 'partial':
        return 'exclude_partial'
    if diag == 'candidate_aggregation':
        return 'reached_but_unused'
    if diag == 'correct_control':
        return 'correct'
    return 'lost'   # extraction_omission / selection_omission / distortion


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--execute', action='store_true')
    ap.add_argument('--max-calls', type=int, default=540)
    a = ap.parse_args()

    cfg = json.loads(CFG_PATH.read_text())
    dev = json.loads(DEV_CFG.read_text())
    assert cfg['matcher_frozen'] is True
    # The freeze record must still describe the files on disk and the dev settings.
    assert sha(DEV_CFG) == cfg['settings_file_sha256']
    assert digest(dev) == cfg['settings_object_sha256']
    assert PROMPT_SHA256 == cfg['prompt_sha256'] == dev['prompt_sha256']
    assert cfg['version'] == VERSION == dev['version']
    assert cfg['model'] == dev['judge_model']
    assert cfg['temperature'] == dev['temperature'] == 0
    assert cfg['max_tokens'] == dev['max_tokens'] == 4096
    assert cfg['max_retries'] == dev['max_retries'] == 2
    for p, h in cfg['code_sha256'].items():
        assert sha(p) == h, f'code changed since the freeze: {p}'

    ids = anchor_ids()
    from scripts.build_final_author_packet import packages
    pk = packages(set(ids))
    items = [(m, i) for i in ids for m in cfg['source_trace_models']]
    assert len(items) == 90 and all((m, i) in pk for m, i in items)
    OUT = Path(cfg['output'])
    print(json.dumps({'version': VERSION, 'prompt_sha256': PROMPT_SHA256,
                      'traces': len(items), 'execute': a.execute,
                      'max_calls': a.max_calls, 'start_utc': utc()}), flush=True)
    if not a.execute:
        print(json.dumps({'dry_check': 'ok', 'instances': len(ids), 'traces': len(items)}), flush=True)
        return

    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / 'matcher').mkdir(exist_ok=True)
    ledger = CallLedger(OUT, cfg, cfg['prereg'], a.max_calls)
    counts = {'planned': len(items), 'attempted': 0, 'ok': 0, 'failed': 0,
              'failed_keys': [], 'failed_error_types': {}, 'stopped_early': False}
    per_model = {m: {'planned': 30, 'ok': 0, 'failed': 0} for m in cfg['source_trace_models']}
    try:
        for n, (model, inst) in enumerate(items, 1):
            t = adapt(pk[(model, inst)])
            key = digest(['E1-anchor-matcher', 42, inst, model])
            counts['attempted'] += 1
            try:
                result = match_trace(ledger, key, t, cfg['model'])
                rec = {'instance_id': inst, 'model': model, 'k': t.get('k'),
                       'answer_correct': bool(t.get('answer_correct')),
                       'matcher_frozen': True, **result}
                if result['status'] == 'ok':
                    diag = diagnose(result['facts'], result['carriers'], correct=bool(t.get('answer_correct')))
                    rec['diagnosis'] = diag
                    rec['trace_call'] = e1_call(diag)
                    counts['ok'] += 1
                    per_model[model]['ok'] += 1
                else:
                    counts['failed'] += 1
                    per_model[model]['failed'] += 1
                    counts['failed_keys'].append(key)
                    errs = [x.get('error', '') for x in (result.get('facts_call') or {}).get('attempts', [])
                            + (result.get('carrier_call') or {}).get('attempts', []) if x.get('error')]
                    for e in errs:
                        e = e.split(':')[0]
                        counts['failed_error_types'][e] = counts['failed_error_types'].get(e, 0) + 1
            except Exception as exc:   # transport/ledger failure: logged in the ledger, unscored, not retried
                rec = {'instance_id': inst, 'model': model, 'k': t.get('k'),
                       'answer_correct': bool(t.get('answer_correct')),
                       'matcher_frozen': True, 'status': 'failed', 'value': None,
                       'error': type(exc).__name__ + ': ' + str(exc), 'failure_stage': 'call'}
                counts['failed'] += 1
                per_model[model]['failed'] += 1
                counts['failed_keys'].append(key)
                e = type(exc).__name__
                counts['failed_error_types'][e] = counts['failed_error_types'].get(e, 0) + 1
            freeze(OUT / 'matcher' / f'{key}.json', rec)
            status = rec['status'] if rec.get('status') == 'ok' else 'failed'
            print(f"{n}/{len(items)} {status} {model} {inst} {utc()}", flush=True)
            if counts['failed'] > MAX_FAILED:
                counts['stopped_early'] = True
                print(f"STOPPED after {counts['failed']} failed traces (limit {MAX_FAILED}); no retry", flush=True)
                break
    finally:
        ledger.close()

    results = [json.loads(l) for l in (OUT / 'calls.jsonl').read_text().splitlines() if l.strip()]
    res = [r for r in results if r['event'] == 'result']
    counts.update({
        'calls_dispatched': len(res),
        'calls_failed': sum(not r['success'] for r in res),
        'cost_usd': round(sum(r.get('cost_usd') or 0 for r in res), 6),
        'per_model': per_model,
        'end_utc': utc(),
        'config_sha256': digest(cfg),
        'prereg_sha256': digest(Path(cfg['prereg']).read_bytes()),
        'freeze': {'frozen_utc': cfg['frozen_utc'], 'prompt_sha256': cfg['prompt_sha256'],
                   'settings_file_sha256': cfg['settings_file_sha256'],
                   'settings_object_sha256': cfg['settings_object_sha256'],
                   'code_sha256': cfg['code_sha256']},
    })
    (OUT / 'summary.json').write_text(json.dumps(counts, indent=2) + '\n')
    print(json.dumps(counts), flush=True)


if __name__ == '__main__':
    main()