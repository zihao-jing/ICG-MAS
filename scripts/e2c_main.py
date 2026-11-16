"""E2-C main run: 7-trace casebook, 3 released methods x 2 backbones.

    ./run.sh python -m scripts.e2c_main --select
    ./run.sh python -m scripts.e2c_main --run --max-calls 72
"""
import argparse
import glob
import hashlib
import json
from pathlib import Path

from src.audit.official_adapters import run_baselines, verify_external
from src.audit.pilot_common import CallLedger, digest
from src.audit.validation_gate import require

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / 'rebuttal/pilots/20261114_part_b_k1/answers.jsonl'
SEALED = ROOT / 'rebuttal/results/batch1/E1_judge_sealed/outputs'
OUT = ROOT / 'rebuttal/pilots/20261114_e2c_main'
PREREG = ROOT / 'rebuttal/pilots/prereg/E2-C-main.md'
BACKBONES = ['qwen/qwen3-235b-a22b-2507', 'google/gemini-3.6-flash']
SEED = 42


def judge_labels():
    out = {}
    for p in glob.glob(str(SEALED / '*.json')):
        d = json.loads(Path(p).read_text())
        out[(d['instance_id'], d['model'])] = d['parsed']
    return out


def klass(row, lab):
    o = lab.get((row['instance_id'], row['model']))
    if not o:
        return None
    bc, car = o.get('binary_call'), o.get('carriers') or []
    absent = [x for x in car if x.get('checkpoint') == 'pool' and not x.get('unit_ids')]
    pool = [x for x in car if x.get('checkpoint') == 'pool' and x.get('unit_ids')]
    board = [x for x in car if x.get('checkpoint') == 'board' and x.get('unit_ids')]
    if bc == 'reached_but_unused':
        return 'aggregation'
    if bc == 'lost' and absent:
        return 'extraction'
    if bc == 'lost' and pool and not board:
        return 'selection'
    return None


def select():
    e1 = json.loads((ROOT / 'rebuttal/judge/E1-judge-v1.json').read_text())
    require('e1_judge_trace_binary', digest(e1['system']))
    lab = judge_labels()
    rows = [json.loads(l) for l in SRC.read_text().splitlines()]
    chosen = []
    short = {}
    plan = [('silobench', 'extraction', 4), ('silobench', 'selection', 4),
            ('musique', 'aggregation', 2), ('silobench', 'aggregation', 2)]
    for ds, c, k in plan:
        pool = [r for r in rows if r['dataset'] == ds and klass(r, lab) == c]
        pool.sort(key=lambda r: digest(['E2-C-main', SEED, r['model'], r['instance_id']]))
        take = pool[:k]
        short[f'{ds}/{c}'] = {'wanted': k, 'found': len(take)}
        chosen += take
    (OUT).mkdir(parents=True, exist_ok=True)
    (OUT / 'selection.json').write_text(json.dumps(
        {'rule_sha256': hashlib.sha256(PREREG.read_bytes()).hexdigest(),
         'seed': SEED, 'shortfall': short,
         'traces': [{k: r[k] for k in ('trace_id', 'model', 'instance_id', 'dataset', 'n')}
                    for r in chosen]}, indent=1) + '\n')
    print(json.dumps({'selected': len(chosen), 'shortfall': short,
                      'traces': [(r['dataset'], r['model'], r['instance_id']) for r in chosen]},
                     indent=1))
    return chosen


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--select', action='store_true')
    ap.add_argument('--run', action='store_true')
    ap.add_argument('--max-calls', type=int, default=72)
    a = ap.parse_args()
    if verify_external():
        raise SystemExit('external files: ' + '; '.join(verify_external()))
    sel = select() if a.select else None
    if a.select and not a.run:
        return
    if a.run:
        from scripts.e2c_validate import SYSTEM
        require('e2c_attribution_match', digest(SYSTEM))
        man = json.loads((OUT / 'selection.json').read_text())
        rows = {r['trace_id']: r for r in
                (json.loads(l) for l in SRC.read_text().splitlines())}
        chosen = [rows[t['trace_id']] for t in man['traces']]
        cfg = {'output': str(OUT), 'prereg': str(PREREG), 'seed': SEED,
               'temperature': 0, 'max_tokens': 4096,
               'pricing': 'rebuttal/pilots/20261108_preflight/pricing.json'}
        ledger = CallLedger(OUT, cfg, PREREG, a.max_calls)
        results = []
        try:
            for r in chosen:
                key = f"{r['model']}/{r['instance_id']}"
                results.append({'trace_id': r['trace_id'], 'model': r['model'],
                                'instance_id': r['instance_id'], 'dataset': r['dataset'],
                                'outputs': run_baselines(ledger, key, r['trace'], BACKBONES)})
        finally:
            ledger.close()
        (OUT / 'results.json').write_text(json.dumps(results, indent=1) + '\n')
        cost = sum(json.loads(l).get('cost_usd') or 0 for l in
                   (OUT / 'calls.jsonl').read_text().splitlines()
                   if l.strip() and json.loads(l).get('event') == 'result')
        summary = {'traces': len(results), 'calls': sum(o.get('calls', 1)
                   for r in results for o in r['outputs']),
                   'parsed': sum(1 for r in results for o in r['outputs']
                                 if o.get('parsed') or o.get('raw')),
                   'cost_usd': round(cost, 6)}
        (OUT / 'summary.json').write_text(json.dumps(summary, indent=1) + '\n')
        print(json.dumps(summary))


if __name__ == '__main__':
    main()