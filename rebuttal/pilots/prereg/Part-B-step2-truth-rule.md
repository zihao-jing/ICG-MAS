# Part B step 2: truth rule for multi-stage traces (frozen before any call)

2026-11-15. Extends `Part-B-judge-v2.md`. Applies to the two 30-trace validations and to the Opus-CLI
validation run. No prompt text changes.

## Rule

A **valid stage set** for a trace is the set of stages named by the reference (Opus 5.5) label for that trace,
each of which the step-1 review found supported by the trace's evidence. A **method is right** on the trace if
at least one stage it names is in that set. A stage outside the set is wrong even if the method also names a
valid stage.

## Why

Step 1 found that all 12 disagreements across the two validations sit on traces that fail at more than one
stage: in the v2 set, both sides list identical defect sets and differ only on `single` vs `multiple`; in the
v1 set, the judge folds a second defect or splits one. Scoring a method as wrong whenever it names a stage
different from the single "true" stage therefore penalises a correct observation on this population.

## Populations

- **Rescore (existing labels, $0):** the 30 v1 validation traces (`opus_labels.json`, `gemini_labels.json`) and
  the 30 v2 revaluation traces (`reval/opus.json`, `reval/gemini.json`). 60 method labels total.
- **Validation (new transport):** the 30 held-out traces of the frozen k = 1 manifest, labelled by Opus 5.5
  through the local `claude -p` CLI, compared with the stored Gemini 3.6 Flash labels for the same traces. The
  k = 1 pool (176 wrong traces) has 156 used by the manifest (126 main + 30 validation); there is no second set
  of 30 unused traces, so this run re-validates the frozen 30 rather than drawing a new sample. That is stated
  in the report.

## Bars and cap

Same bars as the prompt validation: agreement >= .80 and kappa >= .60, Clopper-Pearson interval on agreement
and instance-cluster bootstrap on kappa (2,000 draws, seed 43). Cap **$0.50** at API-equivalent Opus prices
($4/M prompt, $20/M completion); the CLI's own charge is recorded beside it. Stop at the cap.