"""Build the covered (gold-shard, transmitted-unit) pairs for the four new models (no API calls).

Mirrors `scripts/run_distortion_new_models.py`: Silo-Bench, score_ranked_relay, n5+n10,
alignment score >= 0.05 with a best unit.
"""
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scripts.compute_audit_metrics import (align_gold_to_transmitted, get_gold_units,
                                           get_transmitted_units,
                                           reconstruct_states_and_scores)
from src.eval.silo_bench_loader import load_silobench

OUT = ROOT / 'rebuttal/pilots/20261115_distortion_rescore'
RULE = ROOT / 'rebuttal/pilots/prereg/Strict-fidelity-new-models-v1.md'
PROMPT = ROOT / 'rebuttal/pilots/prereg/strict_fidelity_pair_prompt_v1.json'
RUNS = {
    'geminifl': {'n5': 'run_geminiflashlite_n5', 'n10': 'run_geminiflashlite_n10'},
    'gpt4omini': {'n5': 'run_gpt4omini_n5', 'n10': 'run_gpt4omini_n10'},
    'deepseekr1_32b': {'n5': 'run_deepseekr1_32b_n5', 'n10': 'run_deepseekr1_32b_n10'},
    'gemma31b': {'n5': 'run_gemma31b_n5', 'n10': 'run_gemma31b_n10'},
}
SEED = 47
VAL_N = 120


def sha(s):
    return hashlib.sha256(s.encode()).hexdigest()


def file_sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def build():
    pairs = []
    totals = {}
    for model, dirs in RUNS.items():
        n_total = n_cov = 0
        for tier, run in dirs.items():
            n_agents = 5 if tier == 'n5' else 10
            inst_by_id = {i['id']: i for i in load_silobench(n_agents_filter=n_agents)}
            resp = ROOT / 'results' / run / 'api_responses.jsonl'
            if not resp.exists():
                print('missing', resp, file=sys.stderr)
                continue
            states, scores = reconstruct_states_and_scores(
                [json.loads(l) for l in resp.read_text().splitlines() if l.strip()])
            for inst_id, inst in inst_by_id.items():
                if inst_id not in states:
                    continue
                gold = get_gold_units(inst)
                flat = get_transmitted_units(inst_id, 'score_ranked_relay', states, scores,
                                             n_agents=n_agents)
                if not flat:
                    continue
                aln = align_gold_to_transmitted(gold, flat)
                for (agent_id, gold_text), a in zip(gold, aln):
                    n_total += 1
                    best = a.get('best_unit') if isinstance(a, dict) else None
                    score = a.get('score', 0.0) if isinstance(a, dict) else float(a or 0.0)
                    if score < 0.05 or best is None:
                        continue
                    n_cov += 1
                    pairs.append({'pair_id': sha(f'{model}|{tier}|{inst_id}|{agent_id}')[:16],
                                  'model': model, 'tier': tier, 'instance_id': inst_id,
                                  'agent_id': agent_id, 'score': score,
                                  'gold': gold_text, 'unit': best,
                                  'order': sha(f'{SEED}|dist|{model}|{tier}|{inst_id}|{agent_id}')})
        totals[model] = {'n_total': n_total, 'n_covered': n_cov}
    # stratified validation sample: 150 spread by model, then by score quartile
    val = []
    per_model = VAL_N // len(RUNS)
    for model in RUNS:
        pool = sorted([p for p in pairs if p['model'] == model], key=lambda p: p['order'])
        if len(pool) <= per_model:
            val += pool
            continue
        q = len(pool)
        picks = [pool[int((i + 0.5) * q / per_model)] for i in range(per_model)]
        val += picks
    val.sort(key=lambda p: sha(f'{SEED}|val|{p["pair_id"]}'))
    vset = {p['pair_id'] for p in val}
    for p in pairs:
        p['in_validation'] = p['pair_id'] in vset
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / 'population_pairs.json').write_text(json.dumps(pairs, ensure_ascii=False))
    (OUT / 'validation_sample.json').write_text(json.dumps(val, ensure_ascii=False))
    man = {'recorded_before_any_call': True, 'rule_sha256': file_sha(RULE),
           'prompt_sha256': file_sha(PROMPT), 'seed': SEED,
           'pairs': len(pairs), 'pairs_by_model': dict(Counter(p['model'] for p in pairs)),
           'totals_matching_old_run': totals,
           'validation_sample': len(val),
           'validation_by_model': dict(Counter(p['model'] for p in val)),
           'population_sha256': hashlib.sha256((OUT / 'population_pairs.json').read_bytes()).hexdigest(),
           'validation_sha256': hashlib.sha256((OUT / 'validation_sample.json').read_bytes()).hexdigest(),
           'labeller_model': 'anthropic/claude-haiku-5.5',
           'reference_model': 'anthropic/claude-opus-5.5', 'cap_usd': 4.0}
    (OUT / 'build_manifest.json').write_text(json.dumps(man, indent=1))
    print(json.dumps(man, indent=1))


if __name__ == '__main__':
    build()