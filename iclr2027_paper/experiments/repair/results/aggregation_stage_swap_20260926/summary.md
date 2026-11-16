# Full aggregation model-placement comparison

All 326 frozen `aggregation_gap` cases from the revised decision sheets are included. The original and Gemini-terminal results were saved earlier; the Gemini-middle arm replaces only one preselected agent's extracted units and uses the original model for final aggregation.

## Paper version: task averages across models

Each task score is the unweighted mean of its three baseline-model means. `N` counts selected cases across those models. MuSiQue uses answer F1; Silo-Bench uses exact match.

| Task | N | Original | Gemini terminal | Gemini one-agent middle | Terminal − middle |
| --- | ---: | ---: | ---: | ---: | ---: |
| MuSiQue | 213 | 0.158 | 0.285 | 0.224 | +0.061 |
| Silo-Bench, 5 agents | 56 | 0.000 | 0.326 | 0.060 | +0.266 |
| Silo-Bench, 10 agents | 57 | 0.000 | 0.102 | 0.058 | +0.044 |

## Setting-level diagnostic table

| Setting | N | Original | Gemini terminal | Gemini one-agent middle | Terminal − middle [95% CI] | Terminal better / tied / worse |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| gemma31b_musique | 74 | 0.124 | 0.184 | 0.242 | -0.058 [-0.150, +0.031] | 11 / 47 / 16 |
| gemma31b_silobench_n5 | 15 | 0.000 | 0.200 | 0.133 | +0.067 [-0.133, +0.267] | 2 / 12 / 1 |
| gemma31b_silobench_n10 | 17 | 0.000 | 0.059 | 0.118 | -0.059 [-0.235, +0.118] | 1 / 14 / 2 |
| gpt4omini_musique | 71 | 0.134 | 0.324 | 0.168 | +0.156 [+0.063, +0.248] | 23 / 42 / 6 |
| gpt4omini_silobench_n5 | 22 | 0.000 | 0.409 | 0.045 | +0.364 [+0.182, +0.545] | 8 / 14 / 0 |
| gpt4omini_silobench_n10 | 22 | 0.000 | 0.136 | 0.000 | +0.136 [+0.000, +0.318] | 3 / 19 / 0 |
| qwen235b_musique | 68 | 0.216 | 0.347 | 0.263 | +0.085 [-0.018, +0.176] | 24 / 34 / 10 |
| qwen235b_silobench_n5 | 19 | 0.000 | 0.368 | 0.000 | +0.368 [+0.158, +0.579] | 7 / 12 / 0 |
| qwen235b_silobench_n10 | 18 | 0.000 | 0.111 | 0.056 | +0.056 [-0.111, +0.278] | 2 / 15 / 1 |
| **All settings** | **326** | 0.102 | 0.261 | 0.165 | +0.097 [+0.039, +0.152] | 81 / 209 / 36 |

The 14 source-to-board reviewed cases have mean terminal score 0.214 and mean middle score 0.143. The other 312 retained the earlier coarse audit classification.

The comparison uses one Gemini call in each upgraded arm, but the terminal model receives the full original board while the middle model sees only one private shard. This is a model-placement comparison under a one-Gemini-call budget. It does not by itself prove that each failure was caused by aggregation, or that the audit caused any gain. The terminal responses also predate the new middle run; stochastic decoding can contribute variation. The pooled row mixes MuSiQue answer F1 with Silo-Bench exact match; its 95% CI resamples benchmark instances as clusters because the same instance can appear under several baseline models. Per-setting CIs resample cases.

`comparison_per_case.csv` contains every paired case, selected agent, predictions, scores, and prompt hashes. Each `run_*/` directory retains extraction and aggregation responses and the substituted board.
