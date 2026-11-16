# V8 label re-validation with one label definition in both prompts

Rule `LABEL_RULE_V8.md` (sha256 `218985fc1cc8`); reference labels `reference_labels_v8.json` (sha256 `3162758437d8`), frozen before the Haiku calls. Reference **Gemini 3.6 Flash**; labeller **Claude Haiku 5.5**, prompt v4. 60 fresh MuSiQue instances x 2 checkpoints = 120 cases; spend $0.600314, caps $2.00 reference + $0.50 labeller.

**Carrier (board)**

V5 carrier match rate (unit intersection or both absent) **0.947**; paired carrier-presence agreement **177/187 = 0.947** (95% CI 0.904-0.974); kappa **0.777** - **PASS** against 0.80/0.60.

**Presence (extraction)**

Binary carried agreement **179/187 = 0.957** (95% CI 0.917-0.981); kappa **0.815** (0.656-0.924) - **PASS** against 0.85/0.60.

**Fidelity (board, primary)**

Among facts both label carried, faithful agreement **143/156 = 0.917** (95% CI 0.862-0.955); kappa **0.349** (0.080-0.612) - **FAIL** against 0.85/0.60.

Extraction fidelity (secondary): 135/158 = 0.854 (0.790-0.905), kappa 0.083.

Three-class confusion, board (reference, labeller):

| reference \ labeller | faithful | partial | distorted |
| --- | ---: | ---: | ---: |
| faithful | 139 | 11 | 1 |
| partial | 1 | 3 | 0 |
| distorted | 0 | 0 | 1 |

## What this covers

A PASS is cross-model agreement on these 120 MuSiQue cases, not author ground truth, and only at these checkpoints. A FAIL means the label is not used to replace an old column: the disagreements are read, the prompt is fixed, and the fixed prompt is re-validated on a fresh disjoint set.


**Distortion caveat.** V8 has one reference-distorted fact and one distorted-vs-faithful disagreement; this is far too few to validate the distortion label. No Dist column is validated by this run.
