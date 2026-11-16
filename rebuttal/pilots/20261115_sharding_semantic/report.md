# Shard presence by statement, not token overlap — final numbers

2026-11-15. Rule `Sharding-presence-semantic-v1.md` (sha `b9eb130f…`), prompt `per_fact_points_prompt_v1.json`
(sha `86d84ff6…`), Haiku 5.5. 71 calls, 57 cases, **$0.018639** (projection $0.008815), cap $1.00. Third rule on
the same 89 cases: the gain is **post-hoc**.

An intermediate score file carried Gemini 65/87 and Qwen 63/89. It used a roll-up that mapped a single-atom
`partial` to `absent`; the corrected roll-up (present = every atom present, absent = every atom absent, partial
otherwise) and a second pass over cases the old rule had already called sharding give the numbers below. Both are
reported here so the difference is on record.

## Audit cells on 89

| cell | old | new |
| --- | ---: | ---: |
| Gemini (2 unscored counted wrong) | 61/89 = .685 | **66/89 = .742 [.642, .821]** |
| Qwen | 57/89 = .640 | **64/89 = .719 [.618, .802]** |

The two Gemini cases with no stage are `inj/gpt4omini/4hop1__93963_170667_443779_52195` and
`inj/gemma31b/4hop1__151903_5274_458768_33677` (carrier label `uncertain`); they are counted as wrong, as in the
old 61/89. Resolved-only they are 66/87 and 64/89. By population: Gemini injected 21/30, cohort 45/59 = .763
[.640, .853]; Qwen injected 27/30, cohort 37/59 = .627 [.500, .739].

## Confusion, old and new

Gemini:

| known → audit | old | new |
| --- | ---: | ---: |
| extraction → sharding | 2 | **4** |
| extraction → transmission | 2 | 2 |
| sharding → extraction | 15 | **8** |
| transmission → aggregation | 2 | 2 |
| transmission → extraction | 4 | 4 |
| transmission → sharding | 1 | 1 |
| transmission → uncertain | 2 | 2 |

Qwen:

| known → audit | old | new |
| --- | ---: | ---: |
| extraction → sharding | 1 | 1 |
| extraction → transmission | 11 | 11 |
| sharding → extraction | 9 | **2** |
| sharding → transmission | 6 | 6 |
| sharding → aggregation | 2 | 2 |
| transmission → aggregation | 2 | 2 |
| transmission → extraction | 1 | 1 |

## What each error is

**Gemini extraction → sharding (4; two more than before):** `2hop__723404_58556`, `4hop1__3496_5274_458768_33637`,
`3hop1__593288_720914_41132`, `3hop1__274148_792411_51423`. In each, the fact that Gemini marks missing from the
pool is `absent` from its owning shard under the statement check, so the route moves to sharding while the gold
stage is extraction. The rule is doing what it was built to do; these are its cost. Two of the four
(`723404`, `3496`) were correct under the old rule.

**Gemini sharding → extraction (8; from 15):** the statement check finds the missing fact `present` or `partial`
in the shard, so the trace keeps extraction even though the gold says the shard lost it. Seven of the fifteen stay
extraction; the eighth is `2hop__554145_88622`, where the fact is only `partial` in the shard, which the mapping
does not count as a shard loss — this is the rule's one new sharding-known error.

**Qwen extraction → transmission (11, unchanged):** the Qwen carrier labeller marks the extraction pool
`present` for every fact in these traces, so no shard check runs and the trace routes to the board. The gold stage
is extraction, so this is the labeller reading pool presence that is not there, not the rule. Not new.

**Qwen extraction → sharding (1, unchanged):** `3hop1__715607_792411_51423`, the fact is `absent` from the shard
under the statement check while the gold stage is extraction — the same cost as the Gemini four.

**Qwen sharding → extraction (2,: from 9):** the statement check finds the fact stated or partly stated in the
shard; both remaining ones were already wrong before the rule.

## Labels changed beyond sharding

| old → new | n | can change routing? |
| --- | ---: | --- |
| present → present | 29 | no |
| present → absent | 6 | yes, toward sharding |
| present → partial | 3 | no |
| partial → absent | 12 | yes, toward sharding |
| partial → present | 8 | yes, away from sharding |
| partial → partial | 5 | no |
| absent → absent | 3 | — |
| absent → partial | 4 | yes, away from sharding |
| absent → present | 1 | yes, away from sharding |

Only `absent` counts as a shard loss in the stage mapping, and a trace needs every missing fact to be `absent` for
sharding: 18 fact checks moved toward `absent`, 13 moved away (9 to present, 4 to partial). The 8 present↔partial
changes never move a trace by themselves.

## Effect on the sharding repair

The B6 repair ran on the old routing: 59 cohort instances, 39 extraction arm, 20 sharding arm, 6 supported by a
supplied passage, 0 of 6 repaired. The rule leaves the support gate alone but changes arm membership: in the
cohort, 12 instances move into the sharding arm and 3 out under Gemini; 8 in and 1 out under Qwen. The 0/6 stands
for the old arm; no repair calls were made, and the newly routed instances are untested.

## Movement and breakage

- 8 of the 15 sharding-known cases the Gemini audit called extraction now take sharding; 7 stay extraction.
- 7 of the 9 in the Qwen audit move; 2 stay.
- Correct cases that break: 5 Gemini, 1 Qwen. Wrong cases that become correct: 10 Gemini, 8 Qwen.