"""B6 repair arm routed by the audit's own stage (Step 20).

Same frozen rule and run loop as `scripts/b6_repairs.py` (rule `B6-audit-guided-repairs.md`, sha in the B6 manifest).
Only the routing changes: each case takes the stage the token-overlap audit names (`audit_results.json`, `audit_stage`)
instead of the known stage used in the first B6 run. The 59 rows and their audit shards are unchanged.

    ./.conda-env/bin/python -m scripts.b6_audit_routed --build
    ./.conda-env/bin/python -m scripts.b6_audit_routed --run
"""
import argparse
import hashlib
import json
from pathlib import Path

import scripts.b6_repairs as W

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'rebuttal/pilots/20261116_b6_audit_routed'
SRC_POP = ROOT / 'rebuttal/pilots/20261115_b6_repairs/cases.json'
AUDIT = ROOT / 'rebuttal/pilots/20261113_audit_diagnosis_89/audit_results.json'
CAP_USD = 0.05   # hard cap for this arm; the estimate is about $0.01


def sha_file(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def point_module_at_new_folder():
    W.OUT = OUT
    W.POP = OUT / 'cases.json'
    W.MANIFEST = OUT / 'build_manifest.json'
    W.CALLS = OUT / 'calls.jsonl'
    W.RESULTS = OUT / 'results.jsonl'
    W.AMEND_MANIFEST = OUT / 'amendment_manifest.json'   # absent here: the frozen amendments are re-used by hash
    W.CAP = CAP_USD
    W.CHUNK = 0.02


def build():
    OUT.mkdir(parents=True, exist_ok=True)
    rows = json.loads(SRC_POP.read_text())
    audit = {x['key']: x for x in json.loads(AUDIT.read_text())['items']}
    out = []
    for r in rows:
        a = audit[r['key']]
        nr = dict(r)
        nr['known_stage'] = r['stage']
        nr['stage'] = a['audit_stage']
        out.append(nr)
    (OUT / 'cases.json').write_text(json.dumps(out, ensure_ascii=False))
    man = {'recorded_before_any_call': True,
           'rule_sha256': sha_file(W.RULE),
           'population_sha256': sha_file(OUT / 'cases.json'),
           'audit_sha256': sha_file(AUDIT),
           'source_population_sha256': sha_file(SRC_POP),
           'routing': 'audit_stage (token-overlap audit)',
           'by_routed_stage': {s: sum(1 for x in out if x['stage'] == s) for s in ('extraction', 'sharding')},
           'cap_usd': CAP_USD}
    (OUT / 'build_manifest.json').write_text(json.dumps(man, indent=1))
    print(json.dumps(man, indent=1))


def run():
    point_module_at_new_folder()
    W.run()


def main():
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument('--build', action='store_true')
    g.add_argument('--run', action='store_true')
    a = ap.parse_args()
    if a.build:
        build()
    else:
        run()


if __name__ == '__main__':
    main()
