# E3 Silo-Bench routes from the validated labels (relay, qwen235b)

$0, no model calls. 156 traces. Script `scripts/e3_sb_routing_validated.py`; numbers in `results.json`.
Excluded: {}. Fidelity removal not computed (no validated fidelity label on Silo-Bench).

| removed | changed | share [95% CI] | route changes |
|---|---:|---|---|
| pool | 26/156 | 0.167 [0.116, 0.233] | extraction->aggregation (21); extraction->correct (2); extraction->selection (3) |
| aggregation | 105/156 | 0.673 [0.596, 0.742] | aggregation->correct (105) |

| full route | n |
|---|---:|
| aggregation | 105 |
| correct | 23 |
| extraction | 26 |
| selection | 2 |
