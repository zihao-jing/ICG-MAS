"""Ten fresh wrong k=1 traces from the 64 correct-at-k=3 held-out traces."""
import json
from pathlib import Path

from scripts.part_b_k1 import (MODEL_ID, PREREG, RUNS, build_item, packages, wrong_pool)
from src.audit.pilot_common import CallLedger, digest
from src.eval.data_loader import load_musique
from src.eval.evaluate import answer_f1
from src.eval.silo_bench_loader import load_silobench, silobench_exact_match
from src.protocols.base import extract_answer

OUT = Path('rebuttal/pilots/20261114_part_b_k1/extra')
N = 10
CAP = 0.05


def main():
    from scripts.run_e1_judge import heldout_ids
    held = set(heldout_ids())
    correct = []
    for model, runs in RUNS.items():
        for key in ('mq', 5, 10):
            run = runs[key]
            for row in json.loads((Path('results') / run / 'results.json').read_text())[
                    'instance_results']['score_ranked_relay']:
                if row['id'] in held and row.get('correct'):
                    n = int(row['id'].split('hop')[0]) if key == 'mq' else key
                    correct.append({'model': model, 'instance_id': row['id'], 'run': run,
                                    'dataset': 'musique' if key == 'mq' else 'silobench',
                                    'n': n})
    assert len(correct) == 64, len(correct)
    leftover = wrong_pool()[156:176]
    assert len(leftover) == 20, len(leftover)
    pool = correct + leftover
    pk = packages(pool)
    items = [build_item(r, pk[(r['run'], r['instance_id'])]) for r in pool]
    cfg = {'output': str(OUT), 'prereg': str(PREREG), 'seed': 42,
           'temperature': 0, 'max_tokens': 1024,
           'pricing': 'rebuttal/pilots/20261108_preflight/pricing.json'}
    ledger = CallLedger(OUT, cfg, PREREG, len(items))
    mus = {x['id']: x for x in load_musique()}
    sb = {x['id']: x for x in load_silobench()}
    rows = []
    try:
        for it in items:
            pred = ledger.call(it['trace_id'], it['model_id'], it['messages'],
                               max_tokens=1024, temperature=0)
            ans = extract_answer(pred)
            ok = (answer_f1(ans, mus[it['instance_id']]) >= 1 if it['dataset'] == 'musique'
                  else silobench_exact_match(ans, sb[it['instance_id']]) == 1)
            rows.append(dict(it, answer_text=pred, prediction=ans, answer_correct=ok))
    finally:
        ledger.close()
    spent = sum(json.loads(l).get('cost_usd') or 0 for l in
                (OUT / 'calls.jsonl').read_text().splitlines()
                if l.strip() and json.loads(l).get('event') == 'result')
    wrong = [r for r in rows if not r['answer_correct']]
    wrong.sort(key=lambda r: digest(['Part-B-k1-fresh', 42, r['model'], r['instance_id']]))
    chosen = wrong[:30]
    (OUT / 'fresh_items.json').write_text(json.dumps(
        {'spent': round(spent, 6), 'built': len(rows), 'wrong': len(wrong),
         'items': chosen}, indent=1) + '\n')
    print(json.dumps({'built': len(rows), 'wrong': len(wrong), 'chosen': len(chosen),
                      'spent': round(spent, 6),
                      'ids': [(r['model'], r['instance_id']) for r in chosen]}))


if __name__ == '__main__':
    main()