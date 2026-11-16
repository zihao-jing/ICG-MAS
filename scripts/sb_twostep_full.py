"""Silo-Bench two-step full population run (all 208 traces, pilot traces reused).

Rule `rebuttal/pilots/prereg/Silo-Bench-two-step-full.md`, frozen before any call of this run.
Cap $4.00, truncation stop at 2%.

    ./run.sh python -m scripts.sb_twostep_full --build
    ./run.sh python -m scripts.sb_twostep_full --run
"""
import argparse
import hashlib
import json
from pathlib import Path

import scripts.sb_twostep_pilot as P

ROOT = Path(__file__).resolve().parent.parent
FULL = ROOT / 'rebuttal/pilots/20261115_sb_twostep_full'
RULE = ROOT / 'rebuttal/pilots/prereg/Silo-Bench-two-step-full.md'
POP = FULL / 'population.json'
MANIFEST = FULL / 'build_manifest.json'
PILOT_RESULTS = P.OUT / 'results.jsonl'


def configure():
    P.OUT = FULL
    P.POP = POP
    P.MANIFEST = MANIFEST
    P.CALLS = FULL / 'calls.jsonl'
    P.RESULTS = FULL / 'results.jsonl'
    P.SCORE = FULL / 'score.json'
    P.REPORT = FULL / 'report.md'
    P.RULE = RULE
    P.CAP = 4.0
    P.LABEL = True
    P.FACTS_TOK = 16000


def build():
    configure()
    rows = json.loads(P.SRC.read_text())
    rows.sort(key=lambda r: r['key'])
    FULL.mkdir(parents=True, exist_ok=True)
    assert not P.CALLS.exists(), 'refusing to freeze after calls exist'
    POP.write_text(json.dumps(rows, ensure_ascii=False))
    gold = [len(r['gold_supports']) for r in rows]
    man = {'recorded_before_any_call': True, 'rule_sha256': hashlib.sha256(RULE.read_bytes()).hexdigest(),
           'prompt_sha256': P.file_sha(P.PROMPT), 'equiv_prompt_sha256': P.file_sha(P.EQUIV),
           'population_sha256': P.file_sha(POP), 'traces': len(rows),
           'gold_mean': sum(gold) / len(gold), 'cap_usd': P.CAP, 'chunk_usd': P.CHUNK,
           'truncation_stop': 0.02, 'facts_per_trace_max': 30, 'granularity_factor': 1.2,
           'pilot_traces_reused': 20,
           'pilot_results_sha256': P.file_sha(PILOT_RESULTS)}
    MANIFEST.write_text(json.dumps(man, indent=1))
    # reuse the pilot rows unchanged
    with P.RESULTS.open('a') as f:
        for line in PILOT_RESULTS.read_text().splitlines():
            if line.strip():
                f.write(line + '\n')
    print(json.dumps(man, indent=1))


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--build', action='store_true')
    ap.add_argument('--run', action='store_true')
    a = ap.parse_args()
    if a.build:
        build()
    if a.run:
        configure()
        P.run()