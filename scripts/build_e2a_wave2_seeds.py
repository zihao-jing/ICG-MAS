"""E2-A option C: build and hash the two fresh MuSiQue samples before any call.

Reads the shipped MuSiQue dev split through the same loader the paper's runs use, draws one
100-instance sample per seed with the same stratified rule as E2-A (n=100, min_hops=2), removes the
10 reserved instances, and writes one JSONL file per seed. Then writes `seeds.json` with every input
hash (prereg, runner, wave-1 manifest, instance files), the exact models, the exclusion lists and the
$4.00 cap, so the seeds are frozen before the first API call. No model call is made here.

    python -m scripts.build_e2a_wave2_seeds
"""
import hashlib, json
from pathlib import Path

from src.eval.data_loader import load_musique_sample, DEFAULT_DEV_PATH

OUT = Path('rebuttal/pilots/20261110_e2a_wave2')
SEEDS = [43, 44]
PREREG = Path('rebuttal/pilots/prereg/E2-A.md')
RUNNER = Path('src/eval/run_experiment.py')
WAVE1 = Path('rebuttal/pilots/20261108_review5/E2A_combined_manifest.json')
RESERVED = ['2hop__16267_25719', '2hop__24661_81961', '2hop__466700_214359', '2hop__532383_768138',
            '2hop__66708_573255', '2hop__809096_491515', '3hop1__131783_131926_13165',
            '3hop1__169494_42197_18397', '3hop1__273571_834494_33939', '3hop1__273571_834494_34053']
MODELS = {'qwen235b': 'qwen/qwen3-235b-a22b-2507',
          'gpt4omini': 'openai/gpt-4o-mini',
          'gemma31b': 'google/gemma-4-31b-it'}
CAP = 4.00


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    wave1 = json.loads(WAVE1.read_text())
    w1_bases = sorted((c['instance_id'], c['model_family']) for c in wave1['candidates'])
    w1_instances = sorted({i for i, _ in w1_bases})
    seeds = {}
    for seed in SEEDS:
        inst = load_musique_sample(n=100, seed=seed, min_hops=2)
        kept = [x for x in inst if x['id'] not in set(RESERVED)]
        dropped = sorted(x['id'] for x in inst if x['id'] in set(RESERVED))
        path = OUT / f'instances_seed{seed}.jsonl'
        path.write_text(''.join(json.dumps(x, ensure_ascii=False) + '\n' for x in kept))
        seeds[str(seed)] = {'instances_file': str(path), 'instances_sha256': sha(path),
                            'instances': len(kept), 'reserved_dropped': dropped,
                            'overlap_instances_with_wave1': len(set(x['id'] for x in kept) & set(w1_instances))}
    doc = {
        'purpose': 'E2-A option C: two fresh MuSiQue sampling seeds, score-ranked relay k=1 only',
        'date': '2026-11-10', 'created_utc': __import__('datetime').datetime.now(
            __import__('datetime').timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
        'prereg': {'path': str(PREREG), 'sha256': sha(PREREG)},
        'runner': {'path': str(RUNNER), 'sha256': sha(RUNNER)},
        'data_source': str(DEFAULT_DEV_PATH), 'sampling': 'load_musique_sample(n=100, min_hops=2, seed=S)',
        'protocols': ['score_ranked_relay'], 'k': 1, 'temperature': 0,
        'models': MODELS, 'seeds': seeds,
        'wave1_manifest': {'path': str(WAVE1), 'sha256': sha(WAVE1),
                           'bases_excluded': len(w1_bases), 'instances': len(w1_instances)},
        'reserved_instances_excluded': RESERVED,
        'cost_cap_usd': CAP,
        'run_command': ('python -m src.eval.run_experiment --dataset musique --data <instances_file> '
                        '--musique-sample 0 --model <model> --seed <seed> '
                        '--protocols score_ranked_relay --output <dir>'),
        'note': 'score-ranked relay has no RNG; shards_from_musique is fixed, so a repeated instance '
                'reproduces its wave-1 trace. Bases on the 68 wave-1 (instance, model) pairs are excluded '
                'from yields and counted separately.',
    }
    (OUT / 'seeds.json').write_text(json.dumps(doc, indent=2) + '\n')
    print(json.dumps({'seeds_json_sha256': sha(OUT / 'seeds.json'),
                      'per_seed': {k: {'instances': v['instances'],
                                       'reserved_dropped': v['reserved_dropped'],
                                       'overlap_instances_with_wave1': v['overlap_instances_with_wave1'],
                                       'instances_sha256': v['instances_sha256']}
                                   for k, v in seeds.items()}}, indent=1))


if __name__ == '__main__':
    main()