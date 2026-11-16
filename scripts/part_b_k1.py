"""Part B k=1 manifest and answers (no judge calls).

    ./run.sh python -m scripts.part_b_k1 --prepare
    ./run.sh python -m scripts.part_b_k1 --run --max-calls 156
"""
import argparse
import hashlib
import json
import re
from collections import Counter
from pathlib import Path

from src.audit.critical_fact_validation import (
    build_trace_packages, get_transmitted_units, load_jsonl,
    reconstruct_states_and_scores)
from src.audit.pilot_common import CallLedger, blind_view, digest
from src.eval.data_loader import load_musique
from src.eval.evaluate import answer_f1
from src.eval.silo_bench_loader import load_silobench, silobench_exact_match
from src.protocols.base import extract_answer
from src.protocols.relay import _AGGREGATION_SYSTEM, _build_evidence_board_prompt

ROOT = Path(__file__).resolve().parent.parent
PREREG = ROOT / 'rebuttal/pilots/prereg/Part-B-k1.md'
OUT = ROOT / 'rebuttal/pilots/20261114_part_b_k1'
PRICING = 'rebuttal/pilots/20261108_preflight/pricing.json'
SEED = 42
N_MAIN, N_VAL = 126, 30
CAP_USD = 0.51

RUNS = {
    'qwen235b': {'mq': 'run_qwen235b_musique', 5: 'run_qwen235b_n5', 10: 'run_qwen235b_n10'},
    'gpt4omini': {'mq': 'run_musique_gpt4omini', 5: 'run_gpt4omini_n5', 10: 'run_gpt4omini_n10'},
    'gemma31b': {'mq': 'run_musique_gemma31b', 5: 'run_gemma31b_n5', 10: 'run_gemma31b_n10'},
}
MODEL_ID = {
    'qwen235b': 'qwen/qwen3-235b-a22b-2507',
    'gpt4omini': 'openai/gpt-4o-mini',
    'gemma31b': 'google/gemma-4-31b-it',
}


def wrong_pool():
    from scripts.run_e1_judge import heldout_ids
    held = set(heldout_ids())
    recs = []
    for model, runs in RUNS.items():
        for key in ('mq', 5, 10):
            run = runs[key]
            rows = json.loads((ROOT / 'results' / run / 'results.json').read_text())[
                'instance_results']['score_ranked_relay']
            for row in rows:
                inst = row['id']
                if inst not in held or row.get('correct'):
                    continue
                n = int(re.match(r'(\d)hop', inst).group(1)) if key == 'mq' else key
                recs.append({'model': model, 'instance_id': inst, 'run': run,
                             'dataset': 'musique' if key == 'mq' else 'silobench', 'n': n})
    recs.sort(key=lambda r: digest([42, r['model'], r['instance_id']]))
    return recs


def packages(recs):
    out = {}
    by_run = {}
    for r in recs:
        by_run.setdefault((r['dataset'], r['run'], r['n']), []).append(r['instance_id'])
    for (dataset, run, n), ids in by_run.items():
        pk = build_trace_packages(dataset=dataset, run_dir=str(ROOT / 'results' / run),
                                 protocol='score_ranked_relay', source_id=run,
                                 n_agents=None if dataset == 'musique' else n)
        for t in pk:
            out[(run, t['instance_id'])] = t
    return out


def build_item(rec, trace):
    run, inst, n = rec['run'], rec['instance_id'], rec['n']
    states, scores = reconstruct_states_and_scores(
        load_jsonl(ROOT / 'results' / run / 'api_responses.jsonl'))
    units = get_transmitted_units(inst, 'score_ranked_relay', states, scores, n, k=1)
    board = [{'unit_id': f'k1:a{a}:u{j}', 'agent_id': a, 'text': text}
             for a, texts in sorted(units.items()) for j, text in enumerate(texts)]
    messages = [{'role': 'system', 'content': _AGGREGATION_SYSTEM},
                {'role': 'user', 'content': _build_evidence_board_prompt(
                    [units.get(a, []) for a in range(n)], trace['question'])}]
    view = blind_view(trace)
    view['checkpoints']['transmission'] = board
    view['checkpoints']['board'] = board
    view['answer_text'] = ''
    return {'trace_id': digest(['Part-B-k1', SEED, rec['model'], inst]),
            'model': rec['model'], 'model_id': MODEL_ID[rec['model']],
            'instance_id': inst, 'dataset': rec['dataset'], 'run': run, 'n': n,
            'board': board, 'board_sha256': digest(board),
            'messages': messages, 'prompt_sha256': digest(messages),
            'trace': view}


def prepare():
    recs = wrong_pool()
    assert len(recs) >= N_MAIN + N_VAL, len(recs)
    chosen = recs[:N_MAIN + N_VAL]
    pk = packages(chosen)
    items = [build_item(r, pk[(r['run'], r['instance_id'])]) for r in chosen]
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / 'manifest.json').write_text(json.dumps(
        {'rule_sha256': hashlib.sha256(PREREG.read_bytes()).hexdigest(),
         'wrong_pool': len(recs), 'main': N_MAIN, 'validation': N_VAL,
         'items': items}, indent=1) + '\n')
    (OUT / 'manifest.sha256').write_text(
        hashlib.sha256((OUT / 'manifest.json').read_bytes()).hexdigest() + '\n')
    print(json.dumps({'wrong_pool': len(recs), 'items': len(items),
                      'n_sum': sum(i['n'] for i in items),
                      'main_last': items[N_MAIN - 1]['trace_id'],
                      'val_first': items[N_MAIN]['trace_id'],
                      'manifest_sha256': (OUT / 'manifest.sha256').read_text().strip()}))


def run(max_calls):
    man = json.loads((OUT / 'manifest.json').read_text())
    assert max_calls >= len(man['items'])
    cfg = {'output': str(OUT), 'prereg': str(PREREG), 'seed': SEED,
           'temperature': 0, 'max_tokens': 1024, 'pricing': PRICING}
    ledger = CallLedger(OUT, cfg, PREREG, max_calls)
    mus = {x['id']: x for x in load_musique()}
    sb = {x['id']: x for x in load_silobench()}
    ledger_path = OUT / 'calls.jsonl'
    spent = sum(json.loads(l).get('cost_usd') or 0 for l in ledger_path.read_text().splitlines()
                if l.strip() and json.loads(l).get('event') == 'result') if ledger_path.exists() else 0.0
    rows = []
    try:
        for it in man['items']:
            pred = ledger.call(it['trace_id'], it['model_id'], it['messages'],
                               max_tokens=1024, temperature=0)
            spent = sum(json.loads(l).get('cost_usd') or 0 for l in
                        (OUT / 'calls.jsonl').read_text().splitlines()
                        if l.strip() and json.loads(l).get('event') == 'result')
            if spent > CAP_USD:
                raise RuntimeError(f'cost cap: {spent}')
            ans = extract_answer(pred)
            if it['dataset'] == 'musique':
                correct = answer_f1(ans, mus[it['instance_id']]) >= 1
            else:
                correct = silobench_exact_match(ans, sb[it['instance_id']]) == 1
            row = dict(it, answer_text=pred, prediction=ans, answer_correct=correct,
                       answer_sha256=digest(pred))
            rows.append(row)
            print(json.dumps({'done': len(rows), 'spent': round(spent, 6)}), flush=True)
    finally:
        ledger.close()
    (OUT / 'answers.jsonl').write_text('\n'.join(json.dumps(r) for r in rows) + '\n')
    (OUT / 'answers_manifest.json').write_text(json.dumps(
        {'items': [{k: r[k] for k in ('trace_id', 'model', 'instance_id', 'board_sha256',
                                      'prompt_sha256', 'answer_sha256', 'answer_correct')}
                   for r in rows]}, indent=1) + '\n')
    (OUT / 'answers_manifest.sha256').write_text(
        hashlib.sha256((OUT / 'answers_manifest.json').read_bytes()).hexdigest() + '\n')
    print(json.dumps({'items': len(rows), 'spent': round(spent, 6),
                      'correct': sum(r['answer_correct'] for r in rows),
                      'n_dist': dict(sorted(Counter(r['n'] for r in rows).items())),
                      'manifest_sha256': (OUT / 'answers_manifest.sha256').read_text().strip()}))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--prepare', action='store_true')
    ap.add_argument('--run', action='store_true')
    ap.add_argument('--max-calls', type=int, default=156)
    a = ap.parse_args()
    if a.prepare:
        prepare()
    if a.run:
        run(a.max_calls)


if __name__ == '__main__':
    main()