# Injection screening with the labeller gate — pilot

Rule `SCREENING_RULE.md` (sha256 `1a36e5a7cda8`); gate amendment `GATE_AMENDMENT_V1.md` (sha256 `789b36e08cb1`). Spend $0.046534.

**Superseded v2 pass.** v2 called 43/48 bases CORRECT and 6/12 pair sides CORRECT. Its CORRECT is answer-based, so it cannot certify a base defect-free; these calls stay on record and are not the gate result.

**Bases defect-free (evidence-only gate):** 4/47 (8.5%, 95% CI 2.4-20.4%).

| cell | n | defect-free | defective |
| --- | ---: | ---: | ---: |
| 43:gemma31b | 8 | 1 | 7 |
| 43:gpt4omini | 8 | 1 | 7 |
| 43:qwen235b | 8 | 0 | 8 |
| 44:gemma31b | 8 | 0 | 8 |
| 44:gpt4omini | 7 | 2 | 5 |
| 44:qwen235b | 8 | 0 | 8 |

**Injected pairs** (before defect-free, after not):

| item | fault | before | after | gate |
| --- | --- | --- | --- | --- |
| 15eef96e0f7f | extraction_omission | False | False | fail |
| 26d25a11afa9 | extraction_omission | False | False | fail |
| 50c5cd44cae6 | selection_omission | False | False | fail |
| 8386de13b9f5 | distortion | False | False | fail |
| e5a927d12c2f | aggregation | False | False | board unchanged |
| f5c5477fa13b | selection_omission | False | False | fail |

Evidence-fault pairs passing: **0/5** (0.0%, 95% CI 0.0-52.2%); 1 aggregation pair(s) cannot be confirmed by an evidence-only gate (board unchanged by design).

## Spot-check against the real content

Base items agreeing: **2/6**. Evidence-fault pairs agreeing: **0/4**; 2 pair(s) not confirmable by an evidence-only gate.

| item | kind | hand | gate | agrees |
| --- | --- | --- | --- | --- |
| f7990fde4de0 | base | defect_free | defect_free | yes |
| b7a250946325 | base | defect_free | defect_present | no |
| ef980c2a1d19 | base | defect_free | defect_present | no |
| d57d523a9e33 | base | defect_free | defect_present | no |
| 14eb3f16dd80 | base | defect_present | defect_present | yes |
| 3687e6f3af90 | base | defect_free | defect_present | no |
| 50c5cd44cae6 | selection_omission | before free, after defect | before defect, after defect | no |
| e5a927d12c2f | aggregation | before free, after free | before defect, after defect | not confirmable |
| 15eef96e0f7f | extraction_omission | before free, after defect | before defect, after defect | no |
| f5c5477fa13b | selection_omission | before free, after defect | before defect, after defect | no |
| 8386de13b9f5 | distortion | before free, after free | before defect, after defect | not confirmable |
| 26d25a11afa9 | extraction_omission | before free, after defect | before defect, after defect | no |

Notes:

- f7990fde4de0 (base): board carries both critical facts (born in Ronda; Taifa 1039-1065)
- b7a250946325 (base): board carries Kim Il-sung revising the war plan; the other support is river background
- ef980c2a1d19 (base): board carries the SEALs name expansion; destroyer and USS Sanderling supports are distractors
- d57d523a9e33 (base): board carries Abel Tasman discovering New Zealand 1642; the Winter Olympics support is non-critical
- 14eb3f16dd80 (base): board drops that the town Malko Tarnovo is inside Malko Tarnovo Municipality; only the province remains
- 3687e6f3af90 (base): board carries Wipac in Buckingham and the River Great Ouse near Buckingham
- 50c5cd44cae6 (pair): before carries Qiantong-in-Ninghai and Ninghai-in-Ningbo; after replaces the Qiantong unit, breaking the chain
- e5a927d12c2f (pair): board identical before and after; the answer changes UBC to Toronto, so the fault is in aggregation and an evidence-only gate cannot see it
- 15eef96e0f7f (pair): after replaces the Berton-UBC unit with Cindy Marano at Northwestern
- f5c5477fa13b (pair): after replaces the Berton-UBC unit with a book-title fact
- 8386de13b9f5 (pair): after changes a non-critical publication date 1963 to 1964; the gold fact is the household income, which is unchanged
- 26d25a11afa9 (pair): after replaces the Bennett unit with a Max Landis/Elizabeth Gillies unit

