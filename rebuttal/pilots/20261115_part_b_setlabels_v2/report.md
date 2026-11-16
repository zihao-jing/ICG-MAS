# Part B: independent set-valued stage labels

2026-11-15. Rule `Part-B-setlabels.md` (sha `3c16579e...`). Gemini and Qwen labellers blind to both methods; Opus CLI adjudicates. API-equivalent $0.2353, CLI $0.0796, cap $1.50.

| quantity | value |
| --- | ---: |
| traces | 30 |
| judge any-overlap with reference set | 1.000 [0.886, 1.000] |
| judge mean Jaccard | 0.689 |
| labeller-pair any-overlap | 0.733 |

Bars: any-overlap >= .80 and kappa >= .60. Kappa is not reported when the reference set has no variation in the binary call; the interval above is Clopper-Pearson.

## Ledger
API-equivalent $0.235346; CLI $0.079610.
