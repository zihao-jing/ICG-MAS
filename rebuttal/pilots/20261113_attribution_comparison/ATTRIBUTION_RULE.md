# Published-style attribution comparison on known-stage cases (rule frozen before any call)

Written 2026-11-13, before any judge call. This compares a Who&When-style
LLM failure-attribution judge with the audit's stage diagnosis on cases whose
faulty stage is fixed by construction or by a frozen rule.

## Judge

A single **Gemini 3.6 Flash** judge (`google/gemini-3.6-flash`), temperature
0, reasoning enabled, max_tokens 8192, with the frozen prompt
`attribution_prompt_v1.json`. It is shown the full trace in stage order -
question, each agent's source shard, the extraction pool, transmitted
evidence, the shared board, and the (incorrect) final answer - and must name
one stage from `sharding | extraction | transmission | aggregation` plus the
responsible agent and one reason. It is not shown the gold answer.

This is a **Who&When-style** design (transcript-level LLM attribution), not
the authors' released code or exact prompts. The stage vocabulary is the
audit's, extended with sharding, so the comparison is on the audit's own
stage definitions. That difference is a limitation, not a claimed
reimplementation.

## Populations

1. **Injected distortions, n=30** (`20261113_injected_distortion/accepted.json`).
   The faulty stage is **transmission by construction**: one board unit,
   relayed from a named agent, is replaced with a same-class contradiction.
   The judge sees the corrupted transmission/board unit and the corrupt-arm
   final answer (`answers.jsonl`, arm `corrupt`).
2. **Missing-fact cohort, n=69 traces / 59 instances**
   (`20261113_sharding_diagnosis/results.json`, `cohort_traces`). The target
   fact is missing from the final answer by cohort construction. The frozen
   input-presence rule splits the stage: **42 extraction** (fact in the
   agent's shard) and **27 sharding** (fact absent from every shard). The
   judge sees the trace as saved.

Known-stage labels are fixed before the judge run and written with the
population; no case is selected on judge output.

## Runs and caps

Pilot: first 10 cases (5 injected + 5 cohort, hash order) at cap **$0.50**;
if the JSON parses and cost is in line, the full 99 calls run at cap
**$2.00**. Every call logs intent and result with `cost_usd` to
`calls.jsonl`; results cache to `results.json`.

## Metrics

- Stage accuracy (judge stage == known stage) per population and overall,
  with exact Clopper-Pearson 95% CIs.
- Confusion table (known stage x judge stage).
- Comparison rows: the audit names the stage 30/30 on injected distortions
  (definitional) and 69/69 on the cohort; the lexical checkpoint-drop
  baseline names transmission 0/30 and extraction 42/69.
- Cost of the judge calls.

## Caveats

The judge is an LLM, not a published method's validated output; the
comparison is descriptive. The audit's injected 30/30 is definitional and is
not an accuracy estimate. The cohort's 69/69 comes from the frozen
input-presence rule, which is lexical and can read co-located tokens as
presence. No paper file is edited.