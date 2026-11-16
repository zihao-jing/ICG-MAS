# B5 amendment 1: design A (fixed-fact audit row)

2026-11-15. Amends `B5-attribution-2x2.md` (sha `0441ed1c…`) after the Gemini-backed matcher failed validation
(stage agreement .316, kappa .012 — its own fact generation changes the stage). Frozen before any call of this
phase.

## Design, stated plainly

| row | Qwen column | Gemini column |
| --- | --- | --- |
| Who&When-style judge | whole judge with Qwen-235B (**new**) | whole judge with Gemini 3.6 Flash (earlier run) |
| audit, measured diagnosis | Qwen carriers on Qwen facts (earlier run) | **Gemini carrier labels on the same Qwen facts**, then the same `diagnose_with_sharding` |

The judge row swaps the **whole judge**: same prompt, same case text, different model. The audit row swaps only
the **labelling model on fixed Qwen-derived facts**: the fact set is frozen from the Qwen matcher, and only the
carrier-labelling call changes model. Both rows therefore ask whether the method or the model does the work:
the judge row lets the model regenerate everything from the trace; the audit row holds the facts constant and
changes only who labels the carriers.

This is not the failed design (Gemini regenerating its own facts); that run stays on record.

## Validation of the Gemini labelling step

Same 20 disjoint pairs as the failed validation (seed 44). For each, the frozen Qwen facts are the input; the
carrier step (`CARRIER_PROMPT`, frozen in `src/audit/matcher_v2.py`) is run with Gemini 3.6 Flash.
Reference: the frozen Qwen carrier labels on the same facts.

Unit: one fact x one checkpoint (extraction, board), binary **"a faithful carrier is present"**. Agreement and
Cohen's kappa with an instance-cluster bootstrap (2,000 draws, seed 43). **Bars: agreement >= .80, kappa >= .60.**
Cap $0.5; if it fails, stop and diagnose (no 2x2).

## The 2x2 run

Judge Qwen: 89 calls. Audit Gemini: 89 carrier calls on the frozen facts. Cap **$4.00**, chunks of $1 or less,
every call logged. Transport: Gemini through `single_request` without `response_format` (recorded in the parent
rule); Qwen through the client path.

## Scoring

Unchanged: accuracy per cell with Clopper-Pearson 95% CIs; paired difference between backbones within each row,
paired bootstrap over cases, and the alignment between the two rows stated descriptively.