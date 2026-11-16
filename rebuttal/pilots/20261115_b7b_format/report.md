# B7b: format-constrained direct-insertion rerun

2026-11-15. Pre-registered format fix. Rule `B7b-format-constrained.md` (sha `09fcc313...`). Same 59 cases, boards and inserted facts as B7; Opus 5.5 in both arms; the only change is the frozen instruction to answer with the bare value. Spend $0.560820, cap $1.50.

| arm | earlier model | B7 (Opus, sentence format) | B7b (Opus, bare value) | B7b exact 95% CI | paired B7b minus B7 [95% CI] | paired B7b minus earlier [95% CI] | flips vs B7 better / worse |
| --- | --- | --- | --- | --- | --- | --- | --- |
| insert (fact supplied) | 32/59 (54.2%) | 22/59 (37.3%) | 43/59 (72.9%) | 0.597-0.836 | +0.356 [+0.237, +0.475] | +0.186 [+0.102, +0.288] | 22 / 1 |
| control (board only) | 0/59 (0.0%) | 2/59 (3.4%) | 5/59 (8.5%) | 0.028-0.187 | +0.051 [+0.000, +0.119] | +0.085 [+0.017, +0.153] | 3 / 0 |

Within B7b, insert minus control: +0.644 [+0.525, +0.763].

| label | n | insert | control |
| --- | ---: | ---: | ---: |
| present | 33 | 25 | 3 |
| partial | 6 | 3 | 0 |
| absent | 20 | 15 | 2 |

Scoring: the frozen exact rule (`answer_f1 == 1.0` with aliases), the same rule as B7 and the earlier run. Paired bootstrap over cases, 2,000 draws, seed 43; Clopper-Pearson intervals on counts.

## Status of the earlier results

The earlier frozen-rule run (32/59 insert) and B7's sentence-format result (22/59) stay on record. The post-hoc alias/containment secondary from B7 (47/59 vs 40/59) stays labelled post-hoc and is not used here. B7b is the pre-registered confirmation that B7's drop was a format effect, not a capability effect.

## What this cannot show

The insert arm supplies the missing fact verbatim: it is still an oracle upper bound, not an achievable repair.

## Ledger
Spend $0.560820.
