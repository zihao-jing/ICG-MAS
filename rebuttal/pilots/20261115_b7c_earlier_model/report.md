# B7c: bare-value format with the earlier model; the 2x2 of model and format

2026-11-15. Rule `B7c-format-earlier-model.md` (sha `597b79c0...`). Same 59 cases, boards and inserted facts as the original run; the model returns to the trace's own, the bare-value instruction is kept from B7b. Spend $0.008461, cap $1.00.

## Model by format, insert arm (exact, n = 59)

| model | sentence format | bare value |
| --- | ---: | ---: |
| earlier (trace) model | 32 | 30 |
| Opus 5.5 | 22 | 43 |

| effect | paired difference [95% CI] |
| --- | --- |
| format, earlier model (B7c minus original) | -0.034 [-0.102, +0.034] |
| format, Opus 5.5 (B7b minus B7) | +0.356 [+0.237, +0.475] |
| model, bare value (B7b minus B7c) | +0.220 [+0.119, +0.322] |
| model, sentence format (B7 minus original) | -0.169 [-0.305, -0.034] |

Control arm: earlier 0, B7 2, B7c 0, B7b 5. Within B7c, insert minus control: +0.508 [+0.390, +0.627].

| label | n | insert | control |
| --- | ---: | ---: | ---: |
| present | 33 | 18 | 0 |
| partial | 6 | 0 | 0 |
| absent | 20 | 12 | 0 |

Scoring: frozen exact rule (`answer_f1 == 1.0` with aliases) in all four cells. Paired bootstrap over cases, 2,000 draws, seed 43; Clopper-Pearson intervals on counts. The two effects are now separated: the format effect is measured with the model held fixed, and the model effect with the format held fixed, in both cases.

## Status of earlier results

The original run (32/59 insert) and B7's sentence-format Opus run (22/59) stay on record as they were. B7's post-hoc containment secondary stays labelled post-hoc and is not used here.

## What this cannot show

The insert arm supplies the missing fact verbatim: it is an oracle upper bound, not an achievable repair.

## Ledger
Spend $0.008461.
