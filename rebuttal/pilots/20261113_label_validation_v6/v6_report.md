# V6 label validation: presence at extraction, fidelity at relay

Rule `LABEL_RULE_V6.md` (sha256 `7fd16a3826a7`); reference labels `reference_labels_v6.json` (sha256 `b7be13e9efff`), frozen before the Haiku calls. Reference **Gemini 3.6 Flash**; labeller **Claude Haiku 5.5**, prompt v3. 60 fresh MuSiQue instances x 2 checkpoints = 120 cases; spend $0.556415, caps $2.00 reference + $0.50 labeller.

**Presence (extraction)**

Binary carried agreement **161/176 = 0.915** (95% CI 0.863-0.952); kappa **0.634** (0.445-0.800) - **PASS** against 0.85/0.60.

**Fidelity (board, primary)**

Among facts both label carried, faithful agreement **124/147 = 0.844** (95% CI 0.775-0.898); kappa **0.264** (0.016-0.491) - **FAIL** against 0.85/0.60.

Extraction fidelity (secondary): 130/145 = 0.897 (0.835-0.941), kappa 0.426.

Three-class confusion, board (reference, labeller):

| reference \ labeller | faithful | partial | distorted |
| --- | ---: | ---: | ---: |
| faithful | 118 | 11 | 6 |
| partial | 6 | 3 | 1 |
| distorted | 0 | 1 | 1 |

## What this covers

A PASS is cross-model agreement on these 120 MuSiQue cases, not author ground truth, and only at these checkpoints. A FAIL means the label is not used to replace an old column: the disagreements are read, the prompt is fixed, and the fixed prompt is re-validated on a fresh disjoint set.

