"""Matched placement run with the transmission cap raised to 2,000 tokens (both arms).

Setup fix after the 12-case pilot (rebuttal/pilots/20261113_placement_redo/trans_cap2000_pilot.json).
Same cases, prompts, shards, models and temperature as results_matched.json; only MAX_TRANS changes.
Old results stay on record. Cap: $10 total.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import scripts.placement_redo as P

P.MAX_TRANS = 2000
P.MATCHED_RESULTS = P.OUT / 'results_matched_cap2000.json'
P.matched(10.0)
