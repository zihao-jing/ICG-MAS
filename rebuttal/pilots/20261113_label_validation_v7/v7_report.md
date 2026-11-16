# V7 label re-validation after the fidelity fix

Rule `LABEL_RULE_V7.md` (sha256 `d25a7d6d960a`); reference labels `reference_labels_v7.json` (sha256 `a0d4da8d225d`), frozen before the Haiku calls. Reference **Gemini 3.6 Flash**; labeller **Claude Haiku 5.5**, prompt v4. 60 fresh MuSiQue instances x 2 checkpoints = 120 cases; spend $0.580195, caps $2.00 reference + $0.50 labeller.

**Carrier (board)**

V5 carrier match rate (unit intersection or both absent) **0.937**; paired carrier-presence agreement **179/190 = 0.942** (95% CI 0.899-0.971); kappa **0.796** - **PASS** against 0.80/0.60.

**Presence (extraction)**

Binary carried agreement **178/190 = 0.937** (95% CI 0.892-0.967); kappa **0.776** (0.624-0.894) - **PASS** against 0.85/0.60.

**Fidelity (board, primary)**

Among facts both label carried, faithful agreement **136/152 = 0.895** (95% CI 0.835-0.939); kappa **0.443** (0.160-0.692) - **FAIL** against 0.85/0.60.

Extraction fidelity (secondary): 134/152 = 0.882 (0.819-0.928), kappa 0.408.

Three-class confusion, board (reference, labeller):

| reference \ labeller | faithful | partial | distorted |
| --- | ---: | ---: | ---: |
| faithful | 128 | 9 | 2 |
| partial | 5 | 5 | 0 |
| distorted | 0 | 0 | 3 |

## What this covers

A PASS is cross-model agreement on these 120 MuSiQue cases, not author ground truth, and only at these checkpoints. A FAIL means the label is not used to replace an old column: the disagreements are read, the prompt is fixed, and the fixed prompt is re-validated on a fresh disjoint set.


**Distortion caveat.** V7 has three reference-distorted facts (all agreed) and two distorted-vs-faithful disagreements; this is far too few to validate the distortion label. No Dist column is validated by this run.
