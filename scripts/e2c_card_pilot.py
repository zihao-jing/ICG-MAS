"""E2-C card pilot: 3 reserved k=1 traces, 3 released methods x 2 backbones.

    ./run.sh python -m scripts.e2c_card_pilot --execute --max-calls 18
"""
import argparse
import hashlib
import json
from pathlib import Path

from src.audit.pilot_common import CallLedger
from src.audit.official_adapters import run_baselines, verify_external

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / 'rebuttal/pilots/20261108_e1_calibration/traces'
PREREG = ROOT / 'rebuttal/pilots/prereg/E2-C-card-pilot.md'
TECH_PREREG = ROOT / 'rebuttal/pilots/prereg/E2-C-technical.md'
OUT = ROOT / 'rebuttal/pilots/20261114_e2c_card_pilot'
BACKBONES = ['qwen/qwen3-235b-a22b-2507', 'google/gemini-3.6-flash']


def sha(obj):
    return hashlib.sha256(json.dumps(obj, sort_keys=True).encode()).hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--execute', action='store_true')
    ap.add_argument('--max-calls', type=int, default=18)
    a = ap.parse_args()
    if verify_external():
        raise SystemExit('external files: ' + '; '.join(verify_external()))
    traces = []
    for p in sorted(SRC.glob('*.json')):
        d = json.loads(p.read_text())
        if d.get('k') == 1:
            traces.append(d)
    traces.sort(key=lambda t: sha(['E2-C-card-pilot', 43, t['model'],
                                   t['instance_id']]))
    chosen = traces[:3]
    ident = {'rule_sha256': hashlib.sha256(PREREG.read_bytes()).hexdigest(),
             'technical_prereg_sha256': (
                 hashlib.sha256(TECH_PREREG.read_bytes()).hexdigest()
                 if TECH_PREREG.exists() else None),
             'traces': [{'model': t['model'], 'instance_id': t['instance_id']}
                        for t in chosen],
             'backbones': BACKBONES, 'calls_planned': 18}
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / 'manifest.json').write_text(json.dumps(ident, indent=1) + '\n')
    print(json.dumps(ident, indent=1), flush=True)
    if not a.execute:
        return
    cfg = {'output': str(OUT), 'prereg': str(PREREG), 'seed': 43,
           'temperature': 0, 'max_tokens': 4096,
           'pricing': 'rebuttal/pilots/20261108_preflight/pricing.json'}
    ledger = CallLedger(OUT, cfg, PREREG, a.max_calls)
    results = []
    try:
        for t in chosen:
            key = f"{t['model']}/{t['instance_id']}"
            out = run_baselines(ledger, key, t, BACKBONES)
            results.append({'model': t['model'], 'instance_id': t['instance_id'],
                            'outputs': out})
    finally:
        ledger.close()
    (OUT / 'results.json').write_text(json.dumps(results, indent=1) + '\n')
    cost = sum((r.get('cost_usd') or 0) for r in
               (json.loads(l) for l in (OUT / 'calls.jsonl').read_text().splitlines()
                if l.strip()) if r.get('event') == 'result')
    parsed = sum(1 for r in results for o in r['outputs']
                 if o.get('parsed', {}).get('parses', bool(o.get('raw'))))
    summary = {'traces': len(results), 'calls': len(results) * 6,
               'cost_usd': round(cost, 6), 'parse_ok': parsed}
    (OUT / 'summary.json').write_text(json.dumps(summary, indent=1) + '\n')
    print(json.dumps(summary, indent=1))


if __name__ == '__main__':
    main()