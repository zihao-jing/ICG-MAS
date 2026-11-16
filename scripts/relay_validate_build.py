"""Build the 30-pair relay validation sample (no calls)."""
import hashlib
import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / 'rebuttal/pilots/20261115_relay_rescore'
OUT = ROOT / 'rebuttal/pilots/20261115_relay_validation'
RULE = ROOT / 'rebuttal/pilots/prereg/Relay-strict-fidelity-validation-v1.md'
PROMPT = ROOT / 'rebuttal/pilots/prereg/strict_fidelity_pair_prompt_v1.json'
SEED = 47
PER = 10


def sha(s):
    return hashlib.sha256(s.encode()).hexdigest()


def file_sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def build():
    pairs = json.loads((SRC / 'population_pairs.json').read_text())
    sample = []
    for prot in ('random_relay', 'score_ranked_relay', 'redundancy_aware_relay'):
        pool = sorted([p for p in pairs if p['protocol'] == prot],
                      key=lambda p: sha(f'{SEED}|relayval|{p["pair_id"]}'))
        sample += pool[:PER]
    assert len(sample) == len({p['pair_id'] for p in sample})
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / 'validation_sample.json').write_text(json.dumps(sample, ensure_ascii=False))
    man = {
        'recorded_before_any_call': True,
        'rule_sha256': file_sha(RULE), 'prompt_sha256': file_sha(PROMPT),
        'source_population_sha256': file_sha(SRC / 'population_pairs.json'),
        'sample_sha256': file_sha(OUT / 'validation_sample.json'),
        'seed': SEED, 'per_protocol': PER,
        'pairs': len(sample), 'by_protocol': dict(Counter(p['protocol'] for p in sample)),
        'by_old_label': dict(Counter(p['old_label'] for p in sample)),
        'labeller_model': 'anthropic/claude-haiku-5.5',
        'reference_model': 'anthropic/claude-opus-5.5',
        'cap_usd': 0.5,
        'selection': [p['pair_id'] for p in sample],
    }
    (OUT / 'build_manifest.json').write_text(json.dumps(man, indent=1))
    print(json.dumps(man, indent=1))


if __name__ == '__main__':
    build()