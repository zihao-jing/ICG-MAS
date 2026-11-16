# Attribution comparison V2: cohort reconciled to the settled 59/20 (rule frozen before any call)

Written 2026-11-13, before the V2 build or any call. `ATTRIBUTION_RULE.md`
(V1) stays on record; V2 supersedes it. No V1 call was made.

## Cohort reconciliation

V1 read the 69 rows of `20261113_sharding_diagnosis/results.json`
(`cohort_traces`): 42 extraction and 27 sharding. Nine missing-fact instances
have two traces each with the same diagnosis, so the trace-level table inflates
the cohort. The settled figures are **59 missing-fact instances: 39 extraction
and 20 sharding** (`cohort_instances` in the same file). V2 uses **one trace
per instance**, chosen deterministically by
`sha256('43|attr-v2|'+instance_id+'|'+fact_id)`; the other 10 traces are
excluded and listed by count. The settled numbers are unchanged.

Cases: 30 injected distortions (known stage transmission by construction) +
59 missing-fact instances (39 extraction, 20 sharding by the frozen
input-presence rule) = **89 cases**. The V1 case file had 99 because of the
trace-level cohort; V2 replaces it.

## Method

A **Who&When-style re-implementation**, not the published method's released
code or exact prompts: one Gemini 3.6 Flash judge, temperature 0, reasoning
enabled, max 8192, frozen prompt `attribution_prompt_v1.json`. It sees the full
trace in stage order (question, source shards, extraction pool, transmitted
evidence, shared board, known-incorrect final answer) and names one stage from
`sharding | extraction | transmission | aggregation`, plus the responsible
agent and a reason. It is not shown the gold answer. The stage vocabulary is
the audit's, extended with sharding; that difference is stated as a limitation.

## Runs and caps

- Pilot: first 10 cases by hash order, cap **$0.50**; report before the full
  run.
- Full: 89 cases, cap **$2.00**, only after the reviewer's approval.
- Every call logs intent and result with `cost_usd`; results cache to
  `results_v2.json`.

## Metrics

Stage accuracy per population and overall, with exact Clopper-Pearson 95%
CIs; a known-stage x judge-stage confusion table; and the audit/baseline
comparison (audit 30/30 and 59/59 are definitional/frozen-rule, not accuracy
estimates; the lexical checkpoint-drop baseline is 0/30 and 39/59). Point
estimates are reported with their intervals; a 59-case cohort gives intervals
too wide to read as precise accuracy.