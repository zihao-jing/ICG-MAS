# B7: direct insertion re-answered by a stronger aggregator

2026-11-15. Rule `B7-strong-aggregator-insertion.md` (sha `5884e99b...`). Same 59 cases, boards and inserted facts as the earlier direct-insertion run; only the answering model changes, to Opus 5.5, in both arms. Spend $0.899740, cap $3.00.

| arm | earlier model | Opus 5.5 | Opus exact 95% CI | paired Opus minus earlier [95% CI] |
| --- | --- | --- | --- | --- |
| insert (fact supplied) | 32/59 (54.2%) | 22/59 (37.3%) | 0.250-0.509 | -0.169 [-0.305, -0.034] |
| control (board only) | 0/59 (0.0%) | 2/59 (3.4%) | 0.004-0.117 | +0.034 [+0.000, +0.085] |

Within the Opus run, insert minus control: +0.339 [+0.220, +0.475]. In the earlier run: +0.542 [+0.424, +0.661].
Insert arm flips under Opus vs the earlier model: 14 worse, 4 better.

## By presence label (insert arm)

| label | n | earlier model | Opus 5.5 | control, earlier / Opus |
| --- | ---: | ---: | ---: | --- |
| present | 33 | 19 | 10 | 0 / 2 |
| partial | 6 | 0 | 1 | 0 / 0 |
| absent | 20 | 13 | 11 | 0 / 0 |

## Secondary check: gold contained in the answer text (post-hoc)

The frozen exact rule scores `About 11,900 people.` as wrong against `11,900`. The stronger aggregator is more verbose, so exact match also measures answer format. This secondary counter (post-hoc, not the arm's scoring rule) counts a case when the gold or an alias appears inside the extracted answer.

| arm | earlier model | Opus 5.5 | paired Opus minus earlier [95% CI] |
| --- | --- | --- | --- |
| insert (fact supplied) | 40/59 (67.8%) | 47/59 (79.7%) | +0.119 [+0.017, +0.237] |
| control (board only) | 1/59 (1.7%) | 6/59 (10.2%) | +0.085 [+0.000, +0.169] |

Scoring: frozen exact rule (`answer_f1 == 1.0` with aliases); paired bootstrap over cases, 2,000 draws, seed 43; Clopper-Pearson intervals on counts.

## What this cannot show

The insert arm supplies the missing fact verbatim, so it remains an oracle upper bound, not an achievable repair. The two counters disagree because exact match also scores answer format; neither says the fact can be routed or extracted without oracle text. Containment can also be true when the answer lists several candidates or restates the question, so it is an upper bound on correctness, not a scoring rule.

## Ledger
Spend $0.899740.
