# B7d: bare-value insertion rerun with a paper model

2026-11-15. Frozen before any call. Cap **$1.50**, chunks of $1 or less.

## Why

Opus 5.5 is the project's labeller and reference, not a paper model, so B7 and B7b cannot carry a result in
the paper. This rerun repeats the stronger-aggregator test with **Gemini 3.6 Flash**, a paper model, and the
same bare-value instruction. The Opus runs stay on record, marked not usable as paper-subject evidence.

## Design

Same 59 cases, `control_board` / `insert_board`, and inserted facts from
`20261112_missing_fact_repair/direct_insertion/cases.json`; Gemini 3.6 Flash in both arms; temperature 0;
`max_tokens=1024`; system instruction is the frozen bare-value note used in B7b/B7c (sha checked against the
B7c manifest), appended to `_AGGREGATION_SYSTEM`. The user prompt is byte-identical to the original run's.

## Comparison, all paired per case

- Gemini bare value vs the original run's trace-model insert (32/59): the paper-model effect, with format held.
- Gemini bare value vs Opus bare value (B7b): model effect at bare format, for reference only.
- Gemini insert vs Gemini control within the run.
- Counts with Clopper-Pearson 95% intervals; paired differences with a case bootstrap (2,000 draws, seed 43).

## Status of the Opus runs

B7 (Opus, sentence format) and B7b (Opus, bare value) remain on record as **not usable** for paper-subject
claims: Opus is our labeller and reference model.