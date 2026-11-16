# Coverage and aggregation-failure re-score — pilot

Rule `SCORING_RULE.md` (sha256 `2d19e61eda75`), prompt `coverage_prompt_v1.json` (sha256 `4f23970adfd9`); output-budget amendment `COVERAGE_AMENDMENT_V1.md`. 119/120 traces scored; 1 unparsed; spend $0.067733.

**Path taken:** `coverage_prompt_v1` was validated against the author carrier labels instead of switching to `labeller_prompt_v2`, because v2 is answer-based and returns no coverage label. The validation is **negative**: agreement 0.389 (see Direction of the difference and `20261113_coverage_validation/report.md`).

| endpoint | k/n | rate | 95% CI |
| --- | ---: | ---: | --- |
| complete coverage, lexical | 20/120 | 16.7% | 10.5-24.6% |
| complete coverage, labeller (not validated) | 27/120 | 22.5% | 15.4-31.0% |
| AF, lexical | 11/120 | 9.2% | 4.7-15.8% |
| AF, labeller (not validated) | 18/120 | 15.0% | 9.1-22.7% |

The labeller columns are **not validated**: the coverage prompt agrees with author labels on 70/180 comparisons (see below).

Denominators are the 120 sampled traces. The one unparsed trace (II-18_n10, redundancy_aware_relay) is scored as not complete and not AF. CIs are exact Clopper-Pearson, not Wilson.

Agreement on complete coverage: **0.825**; Cohen kappa **0.447** (n=120; the unparsed trace counts as not complete for both).

## Per protocol

| protocol | n | lexical complete | labeller complete (not validated) | both AF |
| --- | ---: | ---: | ---: | ---: |
| random_relay | 30 | 5 | 9 | 4 |
| redundancy_aware_relay | 30 | 5 | 7 | 0 |
| score_ranked_relay | 30 | 9 | 9 | 3 |
| summary_exchange | 30 | 1 | 2 | 0 |

## Direction of the difference

Across the 120 sampled traces the labeller calls complete coverage more often than the lexical rule (27 vs 20). The disagreements split 14 labeller-only complete and 7 lexical-only complete. Per protocol the labeller count is higher in random (9 vs 5), redundancy_aware (7 vs 5) and summary_exchange (2 vs 1) and equal in score_ranked (9 vs 9).

This is the opposite direction to the earlier finding that the lexical rule over-counts coverage, and the two rules measure different things. The lexical rule asks whether 80% of a whole support paragraph's content tokens reappear in one board unit. A board that faithfully carries the decisive clause but drops the support's framing, or spreads it over units, falls below 0.8 even though the fact is carried; in the 14 labeller-only cases only 1 of 36 best-support recalls reaches 0.8. That is the labeller-finds-more direction. The 7 lexical-only cases are the other failure: every support's best recall is at least 0.8 (most exactly 1.0), and the labeller rejects them because the board repeats the support as a listing without the fact's relation or a complete restatement. The two measures therefore disagree in both directions, and neither is a one-sided over-count.

**The coverage prompt is not validated.** Against author carrier labels it agrees with **70/180** comparisons (38.9%, exact Clopper-Pearson 95% CI 31.7-46.4%), Cohen kappa **0.031**; it calls coverage complete 58 times where the two authors do so 156 times (`20261113_coverage_validation/report.md`), below the 0.80 agreement threshold fixed in that rule. The labeller column is therefore reported beside the lexical column and is **not** a correction of the paper's coverage or AF figures; the lexical rule stands alone until a validated coverage measure exists.


## Disagreements

| trace | protocol | lexical | labeller (not validated) | f1 |
| --- | --- | ---: | ---: | ---: |
| 2hop__661847_288421 | random_relay | False | True | 0.5 |
| 2hop__307218_161450 | random_relay | False | True | 0.470588 |
| 2hop__151750_141308 | random_relay | False | True | 0.8 |
| 2hop__403060_92763 | random_relay | False | True | 1.0 |
| I-04_n10 | redundancy_aware_relay | True | False | 1.0 |
| 2hop__363216_787353 | redundancy_aware_relay | False | True | 0.333333 |
| 2hop__640262_122868 | redundancy_aware_relay | False | True | 1.0 |
| 2hop__81659_52835 | redundancy_aware_relay | False | True | 1.0 |
| 2hop__846844_47134 | redundancy_aware_relay | False | True | 0.0 |
| 2hop__488811_30113 | redundancy_aware_relay | False | True | 0.255319 |
| II-15_n5 | redundancy_aware_relay | True | False | 0.0 |
| I-03_n10 | redundancy_aware_relay | True | False | 1.0 |
| 2hop__161273_92673 | score_ranked_relay | False | True | 0.230769 |
| 2hop__525581_161450 | score_ranked_relay | False | True | 0.888889 |
| II-15_n5 | score_ranked_relay | True | False | 0.0 |
| II-12_n5 | score_ranked_relay | True | False | 0.0 |
| I-04_n10 | score_ranked_relay | True | False | 1.0 |
| 2hop__661847_288421 | score_ranked_relay | False | True | 0.5 |
| II-12_n5 | summary_exchange | True | False | 0.0 |
| I-02_n10 | summary_exchange | False | True | 0.0 |
| 2hop__640262_122868 | summary_exchange | False | True | 0.470588 |

Unparsed keys (in the sample, not scored): qwen235b|SB|results/run_qwen235b_n10|redundancy_aware_relay|II-18_n10

