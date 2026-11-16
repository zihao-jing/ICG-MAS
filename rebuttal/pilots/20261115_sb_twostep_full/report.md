# Silo-Bench two-step full run: all 208 traces

2026-11-15. Rule `Silo-Bench-two-step-full.md` (sha `a312bcc3…`), amendment 1 (`fb58df80…`, facts cap 16000), prompt
`proxy_facts_prompt_v3_two_step.json` (sha `7210ce14…`). All 208 traces completed. Spend **$2.468869**, cap $4.00.

## Bars

| test | result | verdict |
| --- | --- | --- |
| truncation <= 2% | 1/208 = 0.48% [0.08%, 2.67%] | pass |
| mean facts <= 1.2 x gold | 7.96 vs 7.50 = 1.061 | pass |
| no trace above 30 facts | 1 trace at 60 (`...|score_ranked_relay|III-27_n10`) | **FAIL** |
| no generation failure | 4 traces | **FAIL** |

**The run fails two of the four gates: the 30-fact ceiling (one trace at 60) and the no-generation-failure gate (4 traces).** One trace produced 60 facts, and four traces ended with no
valid fact set after three attempts: `III-30_n5` in random_relay, redundancy_aware_relay and score_ranked_relay,
and `II-17_n5` in redundancy_aware_relay. Generation failures are **4/208 = 1.9%**. All four are n5 traces; each selection call succeeded, the facts stage
did not. The 60-fact trace also carries the run's single truncation flag. None of these traces is dropped; they
stay in the population and are reported.

## Facts and equivalence

1,564 facts generated; Gemini equivalence against the gold supports: **1,535 equivalent = 98.15% [97.35%, 98.71%]**
(Wilson; the Clopper-Pearson computation overflows at this n), 19 partial, 8 unsupported, 2 contradicted.
**Caveat:** the extracted facts are near copies of the gold sentences they are scored against, so this is a
self-consistency check, not a measure of proxy quality; it must not be quoted as one.

## Granularity

Mean facts per trace 7.96 against mean gold supports 7.50; the ceiling breach is the single 60-fact trace above.
The two-step prompt's granularity is otherwise close to gold, which is the property the pilot tested.

## What this supports

The population rate for the two-step pipeline is 208 traces with a 98.15% fact-equivalence rate and a granularity
pass except for one overflow trace and four n5 generation failures. Stage labels were produced with the frozen
per-fact labeller; they are reported separately from the equivalence rate.

## Ledger

$2.468869, cap $4.00. Reused 20 pilot traces; 188 new.
