# Part B: independent set-valued stage labels

2026-11-15. Rule `Part-B-setlabels.md` (sha `f07cbaa6...`). Gemini and Qwen labellers blind to both methods; Opus CLI adjudicates. API-equivalent $1.5241, CLI $0.7017, cap $1.50.

| quantity | value |
| --- | ---: |
| traces | 21 |
| judge any-overlap with reference set | 1.000 [0.845, 1.000] |
| judge mean Jaccard | 0.730 |
| labeller-pair any-overlap | 0.476 |

Bars: any-overlap >= .80 and kappa >= .60. Kappa is not reported when the reference set has no variation in the binary call; the interval above is Clopper-Pearson.

## Ledger
API-equivalent $1.524115; CLI $0.701728.

## Withdrawn

Not usable: the reference set includes Gemini 3.6 Flash, the same model as the stored judge labels, so the
1.000 any-overlap is agreement with itself. The run also closed at **$1.524, $0.024 over the $1.50 cap** (breach).
