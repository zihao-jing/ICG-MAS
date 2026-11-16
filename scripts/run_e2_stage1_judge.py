"""E2-A stage 1: Gemini 3.6 Flash judges the 12 pre-registered wave-1 spot-check items.

Frozen prompt `E2_wave1_base_screening` from `rebuttal/judge/judge_prompts_v3.json`; one call per
item, temperature 0, seed 42, max 10,000 output tokens. No retry: a schema-invalid or failed call is
logged and left unscored. The script never reads an author label, so the judge run is label-blind.

The wave-1 gate (judge vs author `defect_free`) is computed afterwards by
`scripts/analyze_e2_stage1_gate.py`, which is the only script that opens both sides.

Run:
  python -m scripts.run_e2_stage1_judge          # dry check, no calls
  python -m scripts.run_e2_stage1_judge --execute --max-calls 12
"""
import argparse, datetime, hashlib, json, re
from pathlib import Path

from src.audit.pilot_common import CallLedger, digest
from src.audit.judge_render import trace_text

CFG_PATH = Path('rebuttal/pilots/configs/E2-stage1-judge-frozen.json')
MANIFEST = Path('rebuttal/pilots/20261108_review8/e2_spotcheck_wave1_manifest.json')
PRIVATE = Path('rebuttal/pilots/20261108_review8/packet_private_map.json')
PACKET = Path('rebuttal/annotation/author_packet_20261108/E2_spotcheck_wave1.jsonl')
PROMPTS = Path('rebuttal/judge/judge_prompts_v3.json')
TASK = 'E2_wave1_base_screening'
REQUIRED = ['defect_free', 'critical_facts', 'sufficient_support_sets',
            'any_partial_or_distorted_carrier', 'target_checks', 'eligible', 'rationale']


def utc():
    return datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def parse(text):
    s = re.sub(r'^```(?:json)?\s*|\s*```$', '', (text or '').strip())
    i, j = s.find('{'), s.rfind('}')
    if i < 0 or j < i:
        return None, ['no JSON object']
    try:
        o = json.loads(s[i:j + 1])
    except Exception as exc:
        return None, ['invalid JSON: ' + str(exc)[:80]]
    miss = [k for k in REQUIRED if k not in o]
    return o, (['missing keys: ' + ','.join(miss)] if miss else [])


def build_items():
    """The 12 items in the manifest's fixed position order, joined to the packet the authors saw."""
    man = json.loads(MANIFEST.read_text())
    assert sha(MANIFEST) == '75e4211375ecf0972fa5b53d51d8fcf0e2da20965e9382e2b85e2323d3f8e51d'
    priv = json.loads(PRIVATE.read_text())
    rows = [json.loads(l) for l in PACKET.read_text().splitlines() if l.strip()]
    assert sha(PACKET) == '9376547a0e5e38018919533053c179350d69ef9a0b6a589fb860ca7dac18dc26'
    by_key = {(i['fault_type'], i['item_key']): i for i in man['wave1_items']}
    assert len(by_key) == 12
    items = []
    for r in rows:
        p = priv[r['item_id']]
        ft = r['spotcheck_fault_type'].replace(' ', '_')
        m = by_key[(ft, p['item_key'])]
        assert m['author'] == r['assigned_annotator'] and p['item_key'] == m['item_key']
        items.append({'position': m['position'], 'fault_type': ft, 'item_key': m['item_key'],
                      'packet_item_id': r['item_id'], 'author': m['author'],
                      'target_agent': m['target_agent'], 'trace': r['trace']})
    items.sort(key=lambda x: x['position'])
    assert [x['position'] for x in items] == list(range(1, 13))
    return items


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--execute', action='store_true')
    ap.add_argument('--max-calls', type=int, default=12)
    a = ap.parse_args()

    cfg = json.loads(CFG_PATH.read_text())
    prompts = json.loads(PROMPTS.read_text())
    assert cfg['judge_frozen'] is True
    assert sha(PROMPTS) == cfg['prompts_file_sha256']
    assert prompts['prompts_sha256'] == cfg['prompts_sha256']
    p = prompts['prompts'][TASK]
    assert p['judge_model'] == cfg['model'] == 'google/gemini-3.6-flash'
    assert p['system_sha256'] == cfg['system_sha256']
    assert sha('scripts/run_e2_stage1_judge.py') == cfg['code_sha256']['scripts/run_e2_stage1_judge.py'], \
        'runner changed since the freeze'
    assert sha(MANIFEST) == cfg['manifest_sha256']
    assert sha(PACKET) == cfg['packet_sha256']

    items = build_items()
    order_sha = digest([[x['fault_type'], x['item_key']] for x in items])
    assert order_sha == cfg['items_order_sha256'], 'item order changed since the freeze'
    print(json.dumps({'version': cfg['version'], 'prompts_sha256': cfg['prompts_sha256'],
                      'items': len(items), 'order_sha256': order_sha,
                      'execute': a.execute, 'max_calls': a.max_calls, 'start_utc': utc()}), flush=True)
    if not a.execute:
        print(json.dumps({'dry_check': 'ok', 'items': len(items)}), flush=True)
        return

    OUT = Path(cfg['output'])
    (OUT / 'outputs').mkdir(parents=True, exist_ok=True)
    ledger = CallLedger(OUT, {k: cfg[k] for k in ('version', 'model', 'prompts_sha256',
                                                  'prompts_file_sha256', 'max_tokens',
                                                  'temperature', 'seed', 'pricing',
                                                  'items_order_sha256', 'prereg')},
                        cfg['prereg'], a.max_calls)
    counts = {'planned': len(items), 'calls': 0, 'valid': 0, 'format_invalid': 0,
              'failed': 0, 'failed_keys': [], 'format_invalid_keys': [],
              'resolved_models': {}, 'model_mismatch': 0,
              'prompt_tokens': 0, 'completion_tokens': 0, 'cost_usd': 0.0}
    try:
        for n, it in enumerate(items, 1):
            key = digest(['E2-stage1', 42, it['fault_type'], it['item_key']])
            msgs = [{'role': 'system', 'content': p['system']},
                    {'role': 'user', 'content': p['user_template'].format(trace=trace_text(it['trace']))}]
            rec = {'position': it['position'], 'fault_type': it['fault_type'],
                   'item_key': it['item_key'], 'packet_item_id': it['packet_item_id'],
                   'author': it['author'], 'target_agent': it['target_agent'],
                   'messages_sha256': digest(msgs), 'judge_frozen': True}
            try:
                raw = ledger.call(key, cfg['model'], msgs, max_tokens=cfg['max_tokens'], temperature=0)
                parsed, errs = parse(raw)
                rec.update(status='ok' if not errs else 'format_invalid', parsed=parsed,
                           errors=errs, raw=raw)
                counts['valid'] += (not errs)
                counts['format_invalid'] += bool(errs)
                if errs:
                    counts['format_invalid_keys'].append(key)
            except Exception as exc:  # transport/ledger failure: logged, unscored, not retried
                rec.update(status='failed', parsed=None, raw='',
                           errors=['call failed: ' + type(exc).__name__ + ': ' + str(exc)[:160]])
                counts['failed'] += 1
                counts['failed_keys'].append(key)
            counts['calls'] += 1
            r = list(ledger.done.values())[-1] if ledger.done else None
            if r and r.get('key') == key:
                u = r.get('tokens') or {}
                counts['prompt_tokens'] += u.get('prompt_tokens', 0)
                counts['completion_tokens'] += u.get('completion_tokens', 0)
                counts['cost_usd'] += r.get('cost_usd') or 0
                rm = r.get('resolved_model')
                if rm:
                    counts['resolved_models'][rm] = counts['resolved_models'].get(rm, 0) + 1
                    if rm != cfg['model']:
                        counts['model_mismatch'] += 1
            (OUT / 'outputs' / f'{key}.json').write_text(json.dumps(rec, ensure_ascii=False, indent=1))
            print(f"{n}/{len(items)} {rec['status']} pos{it['position']} {utc()}", flush=True)
    finally:
        ledger.close()

    counts['cost_usd'] = round(counts['cost_usd'], 6)
    counts.update({'end_utc': utc(), 'config_sha256': digest(cfg),
                   'prereg_sha256': digest(Path(cfg['prereg']).read_bytes()),
                   'freeze': {'frozen_utc': cfg['frozen_utc'],
                              'prompts_file_sha256': cfg['prompts_file_sha256'],
                              'prompts_sha256': cfg['prompts_sha256'],
                              'system_sha256': cfg['system_sha256'],
                              'code_sha256': cfg['code_sha256']}})
    (OUT / 'summary.json').write_text(json.dumps(counts, indent=1) + '\n')
    print(json.dumps(counts), flush=True)


if __name__ == '__main__':
    main()