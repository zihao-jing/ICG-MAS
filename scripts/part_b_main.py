"""Part B main run: 126 traces, released methods and Gemini judge, dollar-capped batches.

    ./run.sh python -m scripts.part_b_main --cap 3.8 --max-calls 4000
"""
import argparse
import json
import re
from pathlib import Path

from src.audit.judge_render import trace_text
from src.audit.official_adapters import run_baselines, verify_external
from src.audit.pilot_common import CallLedger, digest
from src.audit.validation_gate import require

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / 'rebuttal/pilots/20261114_part_b_k1/answers.jsonl'
OUT = ROOT / 'rebuttal/pilots/20261114_part_b_main'
PREREG = ROOT / 'rebuttal/pilots/prereg/Part-B-main.md'
PROMPTS = ROOT / 'rebuttal/judge/judge_prompts_v3.json'
BACKBONES = ['qwen/qwen3-235b-a22b-2507', 'google/gemini-3.6-flash']
GEMINI = 'google/gemini-3.6-flash'
N = 126


def parse(text):
    s = re.sub(r'^```(?:json)?\s*|\s*```$', '', (text or '').strip())
    a, b = s.find('{'), s.rfind('}')
    if a < 0 or b < a:
        return None
    try:
        o = json.loads(s[a:b + 1])
    except Exception:
        return None
    return o if o.get('class') in ('single', 'multiple', 'indeterminate') else None


def spent():
    p = OUT / 'calls.jsonl'
    if not p.exists():
        return 0.0
    return sum(json.loads(l).get('cost_usd') or 0 for l in p.read_text().splitlines()
               if l.strip() and json.loads(l).get('event') == 'result')


def done():
    p = OUT / 'results.jsonl'
    if not p.exists():
        return set()
    return {json.loads(l)['trace_id'] for l in p.read_text().splitlines() if l.strip()}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--cap', type=float, required=True)
    ap.add_argument('--max-calls', type=int, default=4000)
    a = ap.parse_args()
    if verify_external():
        raise SystemExit('; '.join(verify_external()))
    p = json.loads(PROMPTS.read_text())['prompts']['E2_partB_natural_failure']
    require('partb_natural_failure', digest(p['system']))
    rows = [json.loads(l) for l in SRC.read_text().splitlines()][:N]
    assert len(rows) == N
    seen = done()
    OUT.mkdir(parents=True, exist_ok=True)
    cfg = {'output': str(OUT), 'prereg': str(PREREG), 'seed': 42,
           'temperature': 0, 'max_tokens': 4096,
           'pricing': 'rebuttal/pilots/20261108_preflight/pricing.json'}
    ledger = CallLedger(OUT, cfg, PREREG, a.max_calls)
    try:
        for r in rows:
            if r['trace_id'] in seen:
                continue
            if spent() >= a.cap:
                break
            key = r['trace_id']
            outs = run_baselines(ledger, key, r['trace'], BACKBONES,
                                 step_by_step=True, gold=False)
            msgs = [{'role': 'system', 'content': p['system']},
                    {'role': 'user', 'content': p['user_template'].format(
                        trace=trace_text(r['trace']))}]
            raw = ledger.call(key + '/judge', GEMINI, msgs, max_tokens=2500)
            rec = {'trace_id': key, 'model': r['model'], 'instance_id': r['instance_id'],
                   'dataset': r['dataset'], 'n': r['n'],
                   'outputs': outs, 'judge_raw': raw, 'judge': parse(raw)}
            with (OUT / 'results.jsonl').open('a') as f:
                f.write(json.dumps(rec) + '\n')
            seen.add(key)
            print(json.dumps({'done': len(seen), 'of': N, 'spent': round(spent(), 6),
                              'judge_valid': rec['judge'] is not None}), flush=True)
    finally:
        ledger.close()
    print(json.dumps({'done': len(seen), 'of': N, 'spent': round(spent(), 6),
                      'batch_cap': a.cap}))


if __name__ == '__main__':
    main()