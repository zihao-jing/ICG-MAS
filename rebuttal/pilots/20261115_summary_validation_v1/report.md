# Summary-exchange strict-fidelity validation, v1 (stratified 30 pairs)

2026-11-15. Rule `Summary-strict-validation-v1.md` (sha `37f1439a...`). Prompt `strict_fidelity_pair_prompt_v2.json`. Haiku 5.5 labeller, Opus 5.5 reference. Spend $0.413860, cap $0.50.

| quantity | value [95% CI] |
| --- | --- |
| distorted vs not, agreement | 0.800 [0.654, 0.931] |
| distorted vs not, kappa | 0.167 [-0.123, 0.601] |

**FAILS**

Cells (reference->labeller): absent->absent 6, absent->distorted 1, absent->partial 2, distorted->absent 2, distorted->distorted 1, distorted->partial 3, faithful->faithful 4, faithful->partial 3, partial->absent 3, partial->partial 5

Pairs scored: 30 of 30. Bars: agreement >= .80 and kappa >= .60.

