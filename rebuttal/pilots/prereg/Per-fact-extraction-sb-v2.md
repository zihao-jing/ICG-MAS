# Silo-Bench extraction, fixed prompt: cause and revalidation rule

Date: 2026-11-14. The first Silo-Bench extraction check failed: agreement
.860, kappa .127, with 35 over-credits and 0 misses. This rule is frozen
before the first call of the fixed version.

## Cause, written before any change

All 35 disagreements are the same pattern: a fact whose value is a complete
list of numeric tuples (an agent's shard), and a labeller `partial` on a unit
that states only a few members ("Agent 0 holds 20 data points, including
…"). The reference correctly marks the fact not carried because most members
are missing. The labeller's `partial` is counted as carried, so a missing list
is credited. Examples: `sb/qwen235b/III-25_n10` f1–f10, `III-29_n10` 9 facts,
`III-24_n10` 7 facts, `gpt4omini/III-29_n10` 5 facts. There is no text-fact or
neighbouring-row case.

## Fix

Prompt v4 (`rebuttal/pilots/prereg/per_fact_prompt_v4.json`, system hash
`47cd9e4797046e977c336bb4881203bcb39c958a107a0bd8282c93a6a1032623`) adds
the list-valued rule: a unit that states only some members, or says
"including", is `absent`, not `partial`; `partial` is reserved for a single
claim missing a qualifier.

## Population

30 traces sampled by `sha256('43|extract-sb-v2|model|instance')` from the
**21 Silo-Bench instances not used before**: the 13 instances of the failed
sample, the 18 Part B Silo-Bench instances and the 8 E1 anchor instances are
excluded. Model traces are the sampling unit; the bootstrap clusters by
instance.

## Reference and outcome

Gemini 3.6 Flash with the same frozen extraction-pool prompt as the first
check; labels written and hashed before the Haiku calls. Labeller Claude
Haiku 5.5, prompt v4.

Per-fact presence agreement and Cohen's kappa, with **instance-cluster
bootstrap** CIs (10,000 draws, seed 43), not trace-level CIs. Pass: agreement
>= 0.80 and kappa >= 0.60. If it fails, Silo-Bench extraction stays
exploratory and unvalidated.

## Cost

30 reference and 30 labeller calls, hard cap **$1.00**.