# Main-table redo with the validated per-fact labeller

Rule `REDO_RULE.md` (sha256 `347fadf11935`), frozen before the pilot call; labeller prompt v3 (sha256 `7aeddd80cc3f`). Population: 2,400 Stage 2 MuSiQue traces (800 instances x 3 models, score-ranked relay), 7,665 matcher facts, checkpoints extraction pool and shared board. Scored 4800/4800 checkpoint calls (0 unparsed, scored as absent); spend $1.402666, cap $5.00.

The old column is the frozen audit matcher label on the same facts and checkpoint; the new column is the per-fact labeller. The paper's original Table 3 lexical cells come from the earlier 10-model cohort and are unchanged on record; this redo does not overwrite them. The paper file is not edited; both new columns sit side by side.

Columns: CR = facts with a carrier; complete = all facts in a trace carried; dist = distorted facts / carried facts (fidelity loss); AF = complete coverage and a non-perfect answer.

**Validation caveat.** The labeller is validated for carrier identification at the **board** checkpoint only, and only as cross-model agreement with Gemini 3.6 Flash, not author ground truth. Extraction rows are exploratory; distortion/fidelity labels were not checked by the V5 reference and are unvalidated.

| checkpoint | model | n traces | CR old | CR new | omission old | omission new | complete old | complete new | dist old | dist new | AF old | AF new |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| extraction | gemma31b | 800 | 0.905 | 0.809 | 0.095 | 0.191 | 0.756 | 0.555 | 0.073 | 0.020 | 0.454 | 0.285 |
| extraction | gpt4omini | 800 | 0.961 | 0.896 | 0.039 | 0.104 | 0.874 | 0.711 | 0.029 | 0.033 | 0.541 | 0.414 |
| extraction | qwen235b | 800 | 0.975 | 0.936 | 0.025 | 0.064 | 0.915 | 0.807 | 0.031 | 0.049 | 0.537 | 0.456 |
| board | gemma31b | 800 | 0.905 | 0.813 | 0.095 | 0.187 | 0.756 | 0.568 | 0.074 | 0.017 | 0.454 | 0.295 |
| board | gpt4omini | 800 | 0.959 | 0.894 | 0.041 | 0.106 | 0.870 | 0.705 | 0.028 | 0.039 | 0.539 | 0.404 |
| board | qwen235b | 800 | 0.972 | 0.938 | 0.028 | 0.062 | 0.909 | 0.810 | 0.031 | 0.063 | 0.532 | 0.456 |
| extraction | all | 2400 | 0.947 | 0.881 | 0.053 | 0.119 | 0.848 | 0.691 | 0.044 | 0.035 | 0.511 | 0.385 |
| board | all | 2400 | 0.946 | 0.882 | 0.054 | 0.118 | 0.845 | 0.694 | 0.044 | 0.041 | 0.508 | 0.385 |

## 95% CIs, pooled by checkpoint (instance-cluster bootstrap, seed 43)

| checkpoint | metric | old [95% CI] | new [95% CI] |
| --- | --- | --- | --- |
| extraction | cr | 0.947 [0.940, 0.954] | 0.881 [0.871, 0.890] |
| extraction | complete | 0.848 [0.831, 0.866] | 0.691 [0.667, 0.714] |
| extraction | dist | 0.044 [0.038, 0.050] | 0.035 [0.029, 0.040] |
| extraction | af | 0.511 [0.484, 0.537] | 0.385 [0.360, 0.410] |
| board | cr | 0.946 [0.938, 0.953] | 0.882 [0.872, 0.892] |
| board | complete | 0.845 [0.828, 0.862] | 0.694 [0.670, 0.717] |
| board | dist | 0.044 [0.038, 0.050] | 0.041 [0.035, 0.047] |
| board | af | 0.508 [0.482, 0.535] | 0.385 [0.359, 0.410] |

## MuSiQue answer equivalence (hand-checked by two readers, not author-validated)

From `rebuttal/pilots/20261113_musique_equiv/report.md`. These cells cover the earlier 400-call Qwen-235B main table, not the Stage 2 population above; they are not applied to its AF column.

| protocol | exact | check | delta |
| --- | ---: | ---: | ---: |
| summary_exchange | 19.0% | 53.0% | +34.0 |
| random_relay | 24.0% | 49.0% | +25.0 |
| score_ranked_relay | 28.0% | 53.0% | +25.0 |
| redundancy_aware_relay | 24.0% | 50.0% | +26.0 |
| **pooled** | **23.8%** | **51.2%** | **+27.4** |

The check is confirmed by two hand-check readers, not by author labels; exact cells stay on record unchanged.

## Reading

The board rows are the validated comparison; extraction rows are exploratory and fidelity columns are unvalidated. The labeller and the matcher differ in both directions, so the redo reports both and does not replace the matcher column.
