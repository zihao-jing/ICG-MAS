# Relay strict and broad rates under the v2 prompt

2026-11-15. Rule `Relay-v2-rescore.md` (sha `66efe768...`), prompt `strict_fidelity_pair_prompt_v2.json` (sha `fc725839...`), the prompt validated on this population at kappa .791 [.466, 1.000]. 945 of 945 pairs labelled. Spend $0.353193, cap $0.5.

| cell | pairs | covered | faithful | partial | distorted | absent | strict [95% CI] | broad [95% CI] |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- | --- |
| random_relay | 315 | 282 | 200 | 69 | 13 | 33 | 4.6% [2.5, 7.8] | 29.1% [23.8, 34.8] |
| score_ranked_relay | 315 | 281 | 200 | 69 | 12 | 34 | 4.3% [2.2, 7.3] | 28.8% [23.6, 34.5] |
| redundancy_aware_relay | 315 | 282 | 200 | 69 | 13 | 33 | 4.6% [2.5, 7.8] | 29.1% [23.8, 34.8] |
| pooled | 945 | 845 | 600 | 207 | 38 | 100 | 4.5% [3.2, 6.1] | 29.0% [26.0, 32.2] |

Strict = distorted / covered; broad = (distorted + partial) / covered; absent pairs are listed, not in the denominator. Clopper-Pearson 95% intervals.

The three protocol samples share 302 of their 328 distinct (instance, agent, unit) pairs, so the pooled interval treats repeated units as independent and is too narrow; the protocol rows are the reliable unit of comparison.

The earlier step-9 rates (random 3.2%, score-ranked 4.3%, redundancy 2.9%, pooled 3.5%) were produced under the unvalidated prompt and are not quotable; this table replaces them.

## Ledger
Spend $0.353193.
