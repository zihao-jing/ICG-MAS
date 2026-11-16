"""Re-check the 41 audit-routed repairs that the word-overlap gate rejected (all units undelivered).

Same frozen steps as scripts/b6_gate_recheck.py (validated presence prompt v9, Gemini 3.6 Flash labeller,
answer step as in B6). Only the source population changes: the 41 undelivered rows of
rebuttal/pilots/20261116_b6_audit_routed (36 extraction + 5 sharding). The 0.8 gate is not changed.
Cap $10 total. Output: rebuttal/pilots/20261116_b6_audit_recheck/.

    ./.conda-env/bin/python -m scripts.b6_audit_recheck --build
    ./.conda-env/bin/python -m scripts.b6_audit_recheck --run
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import scripts.b6_gate_recheck as G

ROOT = G.ROOT
G.B6 = ROOT / 'rebuttal/pilots/20261116_b6_audit_routed'
G.OUT = ROOT / 'rebuttal/pilots/20261116_b6_audit_recheck'
G.MANIFEST = G.OUT / 'build_manifest.json'
G.CALLS = G.OUT / 'calls.jsonl'
G.RESULTS = G.OUT / 'results.jsonl'
G.CAP = 10.0
G.rejected = lambda: [r for r in G.b6_rows() if r['status'] == 'undelivered']

if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument('--build', action='store_true')
    g.add_argument('--run', action='store_true')
    a = ap.parse_args()
    G.build() if a.build else G.run()
