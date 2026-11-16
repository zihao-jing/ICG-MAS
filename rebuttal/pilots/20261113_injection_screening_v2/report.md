# Injection screening with the decisive-clause gate — pilot

Amendment `GATE_AMENDMENT_V2.md` (sha256 `d32baad12b43`), prompt `screening_prompt_v2.json` (sha256 `3284d7a08d4d`). Same 48-base / 6-pair sample as the v1 gate; spend $0.018837.

The earlier evidence-only gate (`screening_prompt_v1.json`) and its negative result stay on record in `../20261113_injection_screening/report.md`. This run judges the decisive clause rather than the whole support paragraph.

2 of 48 base calls returned no parseable object; they are excluded from the pass rate and count as gate failures when screening.

**Bases defect-free (decisive-clause gate):** 13/46 (28.3%, 95% CI 16.0-43.5%).

| cell | n | defect-free | defective |
| --- | ---: | ---: | ---: |
| 43:gemma31b | 8 | 4 | 4 |
| 43:gpt4omini | 8 | 2 | 6 |
| 43:qwen235b | 8 | 1 | 7 |
| 44:gemma31b | 8 | 1 | 7 |
| 44:gpt4omini | 6 | 2 | 4 |
| 44:qwen235b | 8 | 3 | 5 |

**Injected pairs** (before defect-free, after not):

| item | fault | before | after | gate |
| --- | --- | --- | --- | --- |
| 15eef96e0f7f | extraction_omission | False | False | fail |
| 26d25a11afa9 | extraction_omission | False | False | fail |
| 50c5cd44cae6 | selection_omission | False | False | fail |
| 8386de13b9f5 | distortion | True | False | pass |
| e5a927d12c2f | aggregation | False | False | board unchanged |
| f5c5477fa13b | selection_omission | False | False | fail |

Evidence-fault pairs passing: **1/5** (20.0%, 95% CI 0.5-71.6%); 1 aggregation pair cannot be confirmed by an evidence-only gate (board unchanged by design).

## Spot-check against real content

| item | hand | gate v2 | agrees | note |
| --- | --- | --- | --- | --- |
| f7990fde4de0 | defect_free | defect_free | yes | board carries both critical facts (born in Ronda; Taifa 1039-1065) |
| b7a250946325 | defect_free | defect_free | yes | board carries Kim Il-sung revising the war plan; the other support is  |
| ef980c2a1d19 | defect_free | defect_present | no | board carries the SEALs name expansion; destroyer and USS Sanderling s |
| d57d523a9e33 | defect_free | defect_present | no | board carries Abel Tasman discovering New Zealand 1642; the Winter Oly |
| 14eb3f16dd80 | defect_present | defect_present | yes | board drops that the town Malko Tarnovo is inside Malko Tarnovo Munici |
| 3687e6f3af90 | defect_free | defect_free | yes | board carries Wipac in Buckingham and the River Great Ouse near Buckin |

Base spot-check agreement: **4/6** (hand labels reused from the v1 screening run; same rendered content).

## Reading

The gate confirms a base clean when every support that carries a decisive clause for the question appears at both checkpoints; pure background supports are marked `not_required`. A base with a real missing fact (e.g. the Malko Tarnovo municipality link) stays defective.

The decisive-clause unit raises the base rate from the v1 gate (4/47, 8.5%) to 13/46 (28.3%) and the hand agreement from 2/6 to 4/6, but it is not yet a reliable screen. Both remaining false defects come from a support that the hand reads as a distractor being marked `required`: ef980c2a1d19 s3 (the USS Sanderling ship) and d57d523a9e33 s1/s4 (the prompt asks for the 1642 date and the author-citizenship link, which the hand treats as secondary). The gate also passes only 1 of 5 evidence-fault pairs (8386de13b9f5, the date distortion).

