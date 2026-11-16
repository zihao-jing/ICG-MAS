"""Build the Silo-Bench population dir under the granularity-fixed proxy (facts prompt v2).

No calls. Reads the 608-trace population, keeps the 208 Silo-Bench rows.
"""
import hashlib
import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / 'rebuttal/pilots/20261115_proxy_support_main_v2/population.json'
OUT = ROOT / 'rebuttal/pilots/20261115_proxy_support_sb_fixed'
RULE = ROOT / 'rebuttal/pilots/prereg/Proxy-support-pilot-v1.md'
AMEND = ROOT / 'rebuttal/pilots/prereg/Proxy-support-pilot-v1-amendment-1.md'
CAPS = ROOT / 'rebuttal/pilots/prereg/Proxy-support-caps-v1.json'
FACTS = ROOT / 'rebuttal/pilots/prereg/proxy_facts_prompt_v2.json'
EQUIV = ROOT / 'rebuttal/pilots/prereg/proxy_support_equiv_prompt_v1.json'
LABELLER = ROOT / 'rebuttal/pilots/20261113_per_fact_labeller/per_fact_prompt_v3.json'


def fsha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def main():
    rows = [r for r in json.loads(SRC.read_text()) if r['benchmark'] == 'SB']
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / 'population.json').write_text(json.dumps(rows, ensure_ascii=False))
    man = {
        'recorded_before_any_call': True,
        'population': 'Silo-Bench 208 traces under the granularity-fixed proxy',
        'rule_sha256': fsha(RULE), 'amendment_sha256': fsha(AMEND),
        'caps_sha256': fsha(CAPS),
        'facts_prompt': 'rebuttal/pilots/prereg/proxy_facts_prompt_v2.json',
        'facts_prompt_sha256': fsha(FACTS),
        'equiv_prompt_sha256': fsha(EQUIV),
        'labeller_prompt_sha256': hashlib.sha256(
            json.loads(LABELLER.read_text())['system'].encode()).hexdigest(),
        'population_sha256': fsha(OUT / 'population.json'),
        'traces': len(rows),
        'by_protocol': dict(Counter(r['protocol'] for r in rows)),
        'with_extraction': sum(1 for r in rows if r.get('has_extraction')),
        'facts_max_tokens': 8000, 'equiv_max_tokens': 8000, 'labeller_max_tokens': 8192,
        'line_cap_usd': 7.5, 'prior_line_spend_usd': 3.586890,
        'remaining_before_this_run_usd': 3.913110,
        'chunk_usd': 1.0, 'chunk_call_cap_usd': 0.90,
    }
    (OUT / 'build_manifest.json').write_text(json.dumps(man, indent=1))
    print(json.dumps(man, indent=1))


if __name__ == '__main__':
    main()