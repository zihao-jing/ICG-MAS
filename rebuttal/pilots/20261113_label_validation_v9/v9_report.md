# V9 label re-validation with the boundary procedure in both prompts

Rule `LABEL_RULE_V9.md` (sha256 `5b4b8123cee3`); reference labels `reference_labels_v9.json` (sha256 `fd5a2da6c474`), frozen before the Haiku calls. Reference **Gemini 3.6 Flash**; labeller **Claude Haiku 5.5**, prompt v9. 60 fresh MuSiQue instances x 2 checkpoints = 120 cases; spend $0.665548, caps $2.00 reference + $0.50 labeller.

**Carrier (board)**

V5 carrier match rate (unit intersection or both absent) **0.947**; paired carrier-presence agreement **180/189 = 0.952** (95% CI 0.912-0.978); kappa **0.796** - **PASS** against 0.80/0.60.

**Presence (extraction)**

Binary carried agreement **183/189 = 0.968** (95% CI 0.932-0.988); kappa **0.857** (0.708-0.955) - **PASS** against 0.85/0.60.

**Fidelity (board, primary)**

Among facts both label carried, faithful agreement **146/159 = 0.918** (95% CI 0.864-0.956); kappa **0.338** (-0.030-0.604) - **FAIL** against 0.85/0.60.

Extraction fidelity (secondary): 149/162 = 0.920 (0.867-0.957), kappa 0.437.

Three-class confusion, board (reference, labeller):

| reference \ labeller | faithful | partial | distorted |
| --- | ---: | ---: | ---: |
| faithful | 142 | 8 | 0 |
| partial | 5 | 4 | 0 |
| distorted | 0 | 0 | 0 |

## What this covers

A PASS is cross-model agreement on these 120 MuSiQue cases, not author ground truth, and only at these checkpoints. A FAIL means the label is not used to replace an old column: the disagreements are read, the prompt is fixed, and the fixed prompt is re-validated on a fresh disjoint set.


**Distortion caveat.** V9 contains **zero distorted facts** among the 159 carried facts, so the distortion label is untested here. No Dist column is validated by this run.
