# B7d: bare-value insertion rerun with a paper model (Gemini 3.6 Flash)

2026-11-15. Rule `B7d-paper-model-aggregator.md` (sha `3c8c5ff5...`). Same 59 cases, boards and inserted facts as the original run; Gemini 3.6 Flash in both arms with the bare-value instruction. Spend $0.221506, cap $1.50.

| arm | earlier trace model, sentence | Gemini 3.6 Flash, bare value | Gemini exact 95% CI | paired Gemini minus earlier [95% CI] |
| --- | --- | --- | --- | --- |
| insert (fact supplied) | 32/59 | 32/59 | 0.408-0.673 | +0.000 [-0.068, +0.068] |
| control (board only) | 0/59 | 1/59 | — | — |

| effect | paired difference [95% CI] |
| --- | --- |
| Gemini bare value minus original trace model (model + format together) | +0.000 [-0.068, +0.068] |
| model at bare format, Opus minus Gemini | +0.186 [+0.085, +0.288] |
| format at Opus, B7b minus B7 | +0.356 [+0.237, +0.475] |
| model at sentence format, Opus minus earlier | -0.169 [-0.305, -0.034] |

Within the Gemini run, insert minus control: +0.525 [+0.407, +0.661].

| label | n | insert | control |
| --- | ---: | ---: | ---: |
| present | 33 | 19 | 1 |
| partial | 6 | 0 | 0 |
| absent | 20 | 13 | 0 |

Scoring: frozen exact rule (`answer_f1 == 1.0` with aliases). Paired bootstrap over cases, 2,000 draws, seed 43; Clopper-Pearson intervals on counts.

## Status of the Opus runs

B7 (Opus, sentence format) and B7b (Opus, bare value) remain on record as **not usable** for paper-subject claims: Opus is the project labeller and reference model.

## What this cannot show

The insert arm supplies the missing fact verbatim, so it measures what the board could answer, not what routing or extraction can deliver.

## Ledger
Spend $0.221506.
