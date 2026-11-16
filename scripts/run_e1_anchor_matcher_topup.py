"""Top-up of the E1 anchor matcher on the 6 never-attempted traces (II-13_n10 and I-02_n5, 3 models each).

The frozen `semantic-dev-v2` is used unchanged: same prompts, schemas, validators, model, temperature,
max_tokens and code. The only difference from the first run is the authorised one-attempt rule: each
logical call (facts, then carriers) is dispatched once, with no schema retry. A call that fails stays
logged and the trace stays unscored. No config file is edited.

Output: rebuttal/results/batch1/E1_matcher_anchor_topup (own ledger and summary; records match the
first run's schema so the analysis can read both directories).

  python -m scripts.run_e1_anchor_matcher_topup --execute
"""
import argparse, datetime, hashlib, json
from pathlib import Path

from src.audit.matcher_v2 import (FACT_PROMPT, CARRIER_PROMPT, PROMPT_SHA256, VERSION,
                                  fact_schema, carrier_schema)
from src.audit.semantic_matcher import validate_facts, validate_carriers, diagnose
from src.audit.matcher_v2 import strict_parse, schema_validate
from src.audit.pilot_common import CallLedger, digest, freeze
from scripts.run_e1_anchor_matcher import CFG_PATH, DEV_CFG, adapt, e1_call

OUT = Path('rebuttal/results/batch1/E1_matcher_anchor_topup')
MISSING = ['II-13_n10', 'I-02_n5']


def utc():
    return datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def one_call(ledger, key, model, system, payload, schema, validator, max_tokens=4096):
    """One dispatch of a frozen matcher call. No retry; a failure is returned, not regenerated."""
    messages = [{'role': 'system', 'content': system + '\nSchema:\n' + json.dumps(schema)},
                {'role': 'user', 'content': json.dumps(payload, ensure_ascii=False)}]
    try:
        raw = ledger.call(key + '/attempt-1', model, messages, max_tokens=max_tokens,
                          response_format={'type': 'json_schema',
                                           'json_schema': {'name': 'audit_output', 'strict': True, 'schema': schema}})
        result = strict_parse(raw)
        schema_validate(result, schema)
        validator(result)
        return {'status': 'ok', 'value': result, 'attempts': [{'attempt': 1, 'valid': True}], 'retried': False}
    except Exception as exc:
        return {'status': 'failed', 'value': None,
                'attempts': [{'attempt': 1, 'valid': False, 'error': type(exc).__name__ + ': ' + str(exc)}],
                'retried': False}


def match_once(ledger, key, trace, model):
    sources = [s['unit_id'] for s in trace['source_supports']]
    f = one_call(ledger, key + '/facts', model, FACT_PROMPT,
                 {'question': trace['question'], 'gold_supports': trace['source_supports']},
                 fact_schema(sources), lambda x: validate_facts(x, sources))
    if f['status'] == 'failed':
        return {'status': 'failed', 'facts_call': f, 'carrier_call': None, 'failure_stage': 'facts'}
    facts = f['value']

    def valid(x):
        validate_carriers(x, facts, trace)
        for row in x['facts']:
            for cp in ('extraction', 'board'):
                for c in row[cp]:
                    if c['role'] == 'joint' and len(c['unit_ids']) < 2:
                        raise ValueError('Joint carrier needs at least two units')
    c = one_call(ledger, key + '/carriers', model, CARRIER_PROMPT,
                 {'question': trace['question'], 'facts': facts, 'source_contexts': trace['source_contexts'],
                  'extraction': trace['checkpoints']['extraction'], 'board': trace['checkpoints']['board']},
                 carrier_schema(facts, trace), valid)
    return {'status': c['status'], 'facts_call': f, 'carrier_call': c,
            'facts': facts, 'carriers': c['value'], 'label_status': 'pilot_provisional'}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--execute', action='store_true')
    a = ap.parse_args()
    cfg = json.loads(CFG_PATH.read_text())
    dev = json.loads(DEV_CFG.read_text())
    assert cfg['matcher_frozen'] is True
    assert sha(DEV_CFG) == cfg['settings_file_sha256']
    assert digest(dev) == cfg['settings_object_sha256']
    assert PROMPT_SHA256 == cfg['prompt_sha256'] == dev['prompt_sha256']
    assert VERSION == cfg['version'] == dev['version']
    assert cfg['model'] == dev['judge_model']
    assert cfg['temperature'] == dev['temperature'] == 0
    assert cfg['max_tokens'] == dev['max_tokens'] == 4096
    for p, h in cfg['code_sha256'].items():
        assert sha(p) == h, f'code changed since the freeze: {p}'
    from scripts.build_final_author_packet import packages
    pk = packages(set(MISSING))
    items = [(m, i) for i in MISSING for m in cfg['source_trace_models']]
    assert len(items) == 6 and all((m, i) in pk for m, i in items)
    print(json.dumps({'version': VERSION, 'prompt_sha256': PROMPT_SHA256, 'traces': len(items),
                      'attempts': 1, 'execute': a.execute, 'start_utc': utc()}), flush=True)
    if not a.execute:
        return
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / 'matcher').mkdir(exist_ok=True)
    ledger = CallLedger(OUT, cfg, cfg['prereg'], 12)
    counts = {'planned': len(items), 'attempted': 0, 'ok': 0, 'failed': 0, 'failed_keys': [],
              'failed_error_types': {}, 'one_attempt': True}
    per_model = {m: {'planned': 2, 'ok': 0, 'failed': 0} for m in cfg['source_trace_models']}
    try:
        for n, (model, inst) in enumerate(items, 1):
            t = adapt(pk[(model, inst)])
            key = digest(['E1-anchor-matcher', 42, inst, model])
            counts['attempted'] += 1
            try:
                result = match_once(ledger, key, t, cfg['model'])
                rec = {'instance_id': inst, 'model': model, 'k': t.get('k'),
                       'answer_correct': bool(t.get('answer_correct')),
                       'matcher_frozen': True, 'one_attempt': True, **result}
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
            except Exception as exc:
                rec = {'instance_id': inst, 'model': model, 'k': t.get('k'),
                       'answer_correct': bool(t.get('answer_correct')), 'matcher_frozen': True,
                       'one_attempt': True, 'status': 'failed', 'value': None,
                       'error': type(exc).__name__ + ': ' + str(exc), 'failure_stage': 'call'}
                counts['failed'] += 1
                per_model[model]['failed'] += 1
                counts['failed_keys'].append(key)
                e = type(exc).__name__
                counts['failed_error_types'][e] = counts['failed_error_types'].get(e, 0) + 1
            freeze(OUT / 'matcher' / f'{key}.json', rec)
            status = 'ok' if rec['status'] == 'ok' else 'failed'
            print(f"{n}/{len(items)} {status} {model} {inst} {utc()}", flush=True)
    finally:
        ledger.close()
    res = [json.loads(l) for l in (OUT / 'calls.jsonl').read_text().splitlines() if l.strip()]
    res = [r for r in res if r['event'] == 'result']
    counts.update({'calls_dispatched': len(res),
                   'calls_failed': sum(not r['success'] for r in res),
                   'cost_usd': round(sum(r.get('cost_usd') or 0 for r in res), 6),
                   'per_model': per_model, 'end_utc': utc(),
                   'runner_sha256': sha(__file__),
                   'config_sha256': digest(cfg),
                   'prereg_sha256': digest(Path(cfg['prereg']).read_bytes()),
                   'freeze': {'frozen_utc': cfg['frozen_utc'], 'prompt_sha256': cfg['prompt_sha256'],
                              'settings_file_sha256': cfg['settings_file_sha256'],
                              'settings_object_sha256': cfg['settings_object_sha256'],
                              'code_sha256': cfg['code_sha256']}})
    (OUT / 'summary.json').write_text(json.dumps(counts, indent=2) + '\n')
    print(json.dumps(counts), flush=True)


if __name__ == '__main__':
    main()