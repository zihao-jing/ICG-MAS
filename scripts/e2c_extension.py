"""E2-C casebook extension: 13 new traces, 3 methods x 2 backbones.

    ./run.sh python -m scripts.e2c_extension --select
    ./run.sh python -m scripts.e2c_extension --run --max-calls 78
    ./run.sh python -m scripts.e2c_extension --judge --max-calls 39
    ./run.sh python -m scripts.e2c_extension --report

The rule `E2-C-extension.md` is hash-checked before every stage. Judge labels
are read only after the 15-trace E2-C validation passes.
"""
import argparse
import glob
import hashlib
import json
import re
from pathlib import Path

from src.audit.judge_render import trace_text
from src.audit.official_adapters import run_baselines, verify_external
from src.audit.pilot_common import CallLedger, digest
from src.audit.validation_gate import require
from scripts.e2c_validate import SYSTEM

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / 'rebuttal/pilots/20261114_part_b_k1/answers.jsonl'
SEALED = ROOT / 'rebuttal/results/batch1/E1_judge_sealed/outputs'
EXISTING = ROOT / 'rebuttal/pilots/20261114_e2c_main/selection.json'
OUT = ROOT / 'rebuttal/pilots/20261114_e2c_extension'
PREREG = ROOT / 'rebuttal/pilots/prereg/E2-C-extension.md'
RULE_SHA256 = 'bc5ac22f43f36e2b9ba66810d609b508164ea035808cbf915ed5400e6962ea95'
BACKBONES = ['qwen/qwen3-235b-a22b-2507', 'google/gemini-3.6-flash']
QWEN = BACKBONES[0]
SEED = 44
CAP_USD = 2.00


def check_rule():
    got = hashlib.sha256(PREREG.read_bytes()).hexdigest()
    if got != RULE_SHA256:
        raise SystemExit(f'rule changed: {got} != {RULE_SHA256}')
    return got


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
    check_rule()
    e1 = json.loads((ROOT / 'rebuttal/judge/E1-judge-v1.json').read_text())
    require('e1_judge_trace_binary', digest(e1['system']))
    lab = judge_labels()
    rows = [json.loads(l) for l in SRC.read_text().splitlines()]
    existing = {(t['instance_id'], t['model']) for t in
                json.loads(EXISTING.read_text())['traces']}
    plan = [('musique', 'extraction', 4), ('musique', 'aggregation', 6),
            ('silobench', 'aggregation', 3)]
    chosen, short = [], {}
    for ds, c, k in plan:
        pool = [r for r in rows if r['dataset'] == ds and klass(r, lab) == c
                and (r['instance_id'], r['model']) not in existing]
        pool.sort(key=lambda r: digest(['E2-C-ext', SEED, r['model'], r['instance_id']]))
        take = pool[:k]
        short[f'{ds}/{c}'] = {'wanted': k, 'found': len(take)}
        chosen += take
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / 'selection.json').write_text(json.dumps(
        {'rule_sha256': check_rule(), 'seed': SEED, 'shortfall': short,
         'existing_casebook': str(EXISTING.relative_to(ROOT)),
         'planned_total': 7 + len(chosen),
         'traces': [{k: r[k] for k in ('trace_id', 'model', 'instance_id', 'dataset', 'n')}
                    for r in chosen]}, indent=1) + '\n')
    print(json.dumps({'new': len(chosen), 'total': 7 + len(chosen),
                      'shortfall': short,
                      'traces': [(r['dataset'], r['model'], r['instance_id']) for r in chosen]},
                     indent=1))
    return chosen


def selected_rows():
    rows = {r['trace_id']: r for r in
            (json.loads(l) for l in SRC.read_text().splitlines())}
    man = json.loads((OUT / 'selection.json').read_text())
    return [rows[t['trace_id']] for t in man['traces']]


def run():
    check_rule()
    if verify_external():
        raise SystemExit('external files: ' + '; '.join(verify_external()))
    chosen = selected_rows()
    cfg = {'output': str(OUT), 'prereg': str(PREREG), 'seed': SEED,
           'temperature': 0, 'max_tokens': 4096,
           'pricing': 'rebuttal/pilots/20261108_preflight/pricing.json'}
    ledger = CallLedger(OUT, cfg, PREREG, 78)
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
    cost = sum(float(json.loads(l).get('cost_usd') or 0) for l in
               (OUT / 'calls.jsonl').read_text().splitlines()
               if l.strip() and json.loads(l).get('event') == 'result')
    summary = {'traces': len(results), 'calls': sum(o.get('calls', 1)
               for r in results for o in r['outputs']),
               'parsed': sum(1 for r in results for o in r['outputs']
                             if o.get('parsed') or o.get('raw')),
               'cost_usd': round(cost, 6)}
    (OUT / 'summary.json').write_text(json.dumps(summary, indent=1) + '\n')
    print(json.dumps(summary))


def parse(text):
    s = re.sub(r'^```(?:json)?\s*|\s*```$', '', (text or '').strip())
    a, b = s.find('{'), s.rfind('}')
    if a < 0 or b < a:
        return None
    try:
        o = json.loads(s[a:b + 1])
    except Exception:
        return None
    return o if o.get('match') in ('yes', 'no', 'uncertain') else None


def judge():
    check_rule()
    require('e2c_attribution_match', digest(SYSTEM))
    import random
    from utility.apis.base import APIRequest
    from utility.apis.openrouter_api import single_request
    GEMINI = 'google/gemini-3.6-flash'
    PRICE = (0.75 / 1e6, 3.75 / 1e6)
    chosen = {r['trace_id']: r for r in selected_rows()}
    rows = json.loads((OUT / 'results.json').read_text())
    out, spent = [], 0.0
    for r in rows:
        for o in r['outputs']:
            if o['backbone'] != QWEN:
                continue
            raw = o.get('raw') or ''
            if isinstance(raw, list):
                raw = '\n'.join(str(x) for x in raw)
            body = (trace_text(chosen[r['trace_id']]['trace'])
                    + '\n\nATTRIBUTION TO CHECK:\n' + raw[:1600])
            key = f"e2c-ext/{r['trace_id']}/{o['method']}"
            resp = single_request(APIRequest(system_query=SYSTEM, user_query=body,
                                             model=GEMINI, max_tokens=1200,
                                             temperature=0,
                                             metadata={'openrouter_reasoning': True}))
            u = resp.usage or {}
            cost = u.get('prompt_tokens', 0) * PRICE[0] + u.get('completion_tokens', 0) * PRICE[1]
            got = parse(resp.content) if resp.success else None
            out.append({'trace_id': r['trace_id'], 'method': o['method'],
                        'success': resp.success, 'valid': got is not None,
                        'parsed': got, 'raw': resp.content,
                        'usage': u, 'cost_usd': round(cost, 8)})
            spent += cost
            if spent > CAP_USD:
                raise RuntimeError(f'cap passed: {spent}')
    (OUT / 'judge_labels.json').write_text(json.dumps(out, indent=1) + '\n')
    (OUT / 'judge_labels.sha256').write_text(
        hashlib.sha256((OUT / 'judge_labels.json').read_bytes()).hexdigest() + '\n')
    summary = {'n': len(out), 'valid': sum(x['valid'] for x in out),
               'cost_usd': round(spent, 6)}
    (OUT / 'judge_summary.json').write_text(json.dumps(summary, indent=1) + '\n')
    print(json.dumps(summary))


def report():
    check_rule()
    rows = json.loads((OUT / 'results.json').read_text())
    labels = json.loads((OUT / 'judge_labels.json').read_text())
    man = json.loads((OUT / 'selection.json').read_text())
    by = {}
    for x in labels:
        if x['valid']:
            by.setdefault(x['trace_id'], {})[x['method']] = x['parsed']
    counts = {'yes': 0, 'no': 0, 'uncertain': 0}
    per_trace = []
    for r in rows:
        d = by.get(r['trace_id'], {})
        vals = [d.get(m, {}).get('match') for m in ('ww_all', 'r1', 'mast')
                if m in d]
        for v in vals:
            if v in counts:
                counts[v] += 1
        sites = {(d[m].get('agent'), d[m].get('stage'))
                 for m in d if d[m].get('match') == 'yes'}
        per_trace.append({'trace_id': r['trace_id'], 'dataset': r['dataset'],
                          'instance_id': r['instance_id'], 'matches': vals,
                          'distinct_yes_sites': len(sites),
                          'any_yes': any(v == 'yes' for v in vals)})
    out = {'new_traces': len(rows), 'total_casebook': man['planned_total'],
           'judge_valid': sum(1 for x in labels if x['valid']),
           'judge_calls': len(labels), 'match_counts': counts,
           'traces_with_any_yes': sum(1 for x in per_trace if x['any_yes']),
           'traces_with_disagreement': sum(1 for x in per_trace
                                           if len({v for v in x['matches'] if v}) > 1),
           'per_trace': per_trace}
    (OUT / 'report.json').write_text(json.dumps(out, indent=1) + '\n')
    print(json.dumps({k: v for k, v in out.items() if k != 'per_trace'}, indent=1))


def main():
    ap = argparse.ArgumentParser()
    for f in ('select', 'run', 'judge', 'report'):
        ap.add_argument('--' + f, action='store_true')
    a = ap.parse_args()
    if a.select:
        select()
    if a.run:
        run()
    if a.judge:
        judge()
    if a.report:
        report()


if __name__ == '__main__':
    main()