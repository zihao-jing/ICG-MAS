# Silo-Bench presence validation

Rule `RULE.md` (sha256 `0b548692f71d`); reference labels `reference_labels.json` (sha256 `32807a58318a`), frozen before the Haiku calls. Reference **Gemini 3.6 Flash**; labeller **Claude Haiku 5.5**. 24 board cases, 180 fact comparisons; spend $0.343337, caps $2.00 + $0.50.

Presence agreement **163/180 = 0.906** (95% CI 0.853-0.944); kappa **0.702** (0.242-0.940) - **PASS** against 0.80/0.60.

| n_agents | agreement | kappa |
| --- | --- | --- |
| n=5 | 54/60 = 0.900 [0.795, 0.962] | 0.446 |
| n=10 | 109/120 = 0.908 [0.842, 0.953] | 0.753 |

A PASS validates the board presence label on Silo-Bench numeric shard facts, cross-model against Gemini, not author ground truth; Silo-Bench rows may then enter the table. A FAIL keeps them out and the cause is reported.

