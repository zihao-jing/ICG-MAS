# Qwen-235B relay strict distortion under the validated label

2026-11-15. Same label and prompt as step 9 (`strict_fidelity_new_models_pairs`, prompt `strict_fidelity_pair_prompt_v1.json`, Haiku 5.5, validated .992 / kappa .937 against Opus 5.5 on 120 pairs). 945 relay pairs from `results/distortion_audit_relay/`; spend **$0.314875**, cap $1.0.

| protocol | pairs | old covered | old strict | old broad | new covered | absent | new strict | new broad |
| --- | ---: | ---: | --- | --- | ---: | ---: | --- | --- |
| random_relay | 315 | 306 | 0.7% [0.1, 2.3] | 24.8% [20.1, 30.1] | 280 | 35 | **3.2% [1.5, 6.0]** | 28.2% [23.0, 33.9] |
| score_ranked_relay | 315 | 307 | 0.3% [0.0, 1.8] | 27.7% [22.8, 33.1] | 281 | 34 | **4.3% [2.2, 7.3]** | 28.5% [23.3, 34.1] |
| redundancy_aware_relay | 315 | 307 | 0.0% [0.0, 1.2] | 26.7% [21.8, 32.0] | 278 | 37 | **2.9% [1.3, 5.6]** | 27.7% [22.5, 33.4] |
| pooled | 945 | 920 | 0.3% [0.1, 0.9] | 26.4% [23.6, 29.4] | 839 | 106 | **3.5% [2.3, 4.9]** | 28.1% [25.1, 31.3] |

Strict = distorted / covered; broad = (distorted + partial) / covered; 95% Clopper-Pearson.
Old covered = pairs the Qwen judge did not mark NO_MATCH (it marks NO_MATCH on any unit with no gold number, so a unit carrying one value counts as covered). New covered = pairs the label does not call absent (the full shard claim is checked). The new label calls absent on 106 of 945 pairs against 25 old NO_MATCH, so the denominators differ; the rate over all eligible pairs is reported below for that reason.

Fixed-denominator strict (distorted / all pairs): random_relay 2.9% [1.3, 5.4], score_ranked_relay 3.8% [2.0, 6.6], redundancy_aware_relay 2.5% [1.1, 4.9], pooled 3.1% [2.1, 4.4]

## Which figure the text will use

**Neither.** The label was revalidated on this population (30 relay pairs, step 9d) and failed the kappa bar:
agreement .933 [.839, 1.000], kappa 0 [-0, 0], because the reference called 2 pairs distorted and the labeller
0, which makes kappa degenerate (record: `20261115_relay_validation/report.md`). Both the Qwen-judge figures and
this re-score therefore stay on record as unvalidated; the text may not quote a strict relay rate until a
validation with enough positive cases passes. The descriptive 3-class agreement on the relay sample is .833.

## 9c. Interval reconciliation

The source report (`protocol_comparison/report.md`) gives the pooled strict rate as 0.3% (0.1-1.0); this table
gives 0.3% [0.1, 0.9]. Both are roundings of the same exact Clopper-Pearson interval for 3/920:
**[0.0673%, 0.94998%]** (verified with two independent implementations, `cp_ci` and a beta-CDF bisection).
At one decimal the upper endpoint 0.94998 rounds to 0.9, not 1.0; the source rounded it up. At two decimals
the interval is [0.07, 0.95]. Neither display changes the reading; the text should quote [0.07, 0.95] or the
count 3/920 to avoid the 0.9/1.0 collision.

## Cross-tab, pooled (old label → new label)

| old \ new | faithful | partial | distorted | absent |
| --- | ---: | ---: | ---: | ---: |
| EXACT | 483 | 92 | 10 | 0 |
| PARAPHRASE | 58 | 30 | 4 | 0 |
| PARTIAL | 59 | 76 | 12 | 93 |
| DISTORTED | 3 | 0 | 0 | 0 |
| NO_MATCH | 0 | 9 | 3 | 13 |

The old judge saw only the shard's key numbers and a 600-character unit; the validated label reads the full shard and the full unit. That difference is part of the comparison.

Scope: the label was validated on 120 score-ranked pairs from the four additional models. Here it is applied to Qwen-235B's three relay protocols with the same prompt and the same relay-checkpoint target; the registration covers the label and prompt, not this population. The pair rendering is identical to step 9 (no question shown).

Of the 3 pairs the old judge called DISTORTED, 3 are faithful under the validated label; 10 units it called EXACT are distorted.

## Ledger
Spend this step $0.314875.
