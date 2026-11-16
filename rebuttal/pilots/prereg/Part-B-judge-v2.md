# Part B judge v2 (frozen before any call)

Date: 2026-11-14. Candidate judge: Gemini 3.6 Flash. Reference: Opus 5.5.
Prompt file: `rebuttal/judge/E2-judge-v2.json`.

The system text is the v3 `E2_partB_natural_failure` system with this block
appended:

> CLASS RULES
> 1. Count an empty or wrong final aggregation as a separate defect whenever
> the board lacks a required unit or the final answer is empty; do not fold it
> into an earlier omission.
> 2. `single` when exactly one listed defect could alone be decisive. List
> other visible defects but do not let them change the class. `multiple` only
> when no single correction suffices.
> 3. An extraction omission stays an extraction defect even if another agent
> later supplies the fact; it is non-decisive then, not relabelled
> transmission.
> 4. Do not answer `indeterminate` because the gold answer is missing from the
> sources. Classify the visible defects; `indeterminate` is reserved for an
> unreadable or incomplete trace.

The user template is unchanged (`RUN TO JUDGE\n{trace}`). The prompt hash is
recorded in the JSON file and must match before any label is written.

## Validation set

30 fresh wrong k = 1 traces, fixed here and disjoint from the 126 main traces,
the 30 earlier validation traces, the 89 known-stage cases and the 7-trace
E2-C casebook:

- 20 wrong traces left after the 126 + 30 draw from the 176-trace pool
  (positions 157-176 of the frozen SHA order);
- 10 traces that were correct at k = 3 but wrong on their k = 1 rebuild,
  drawn by SHA from the 64 correct held-out traces and frozen before any
  judge call.

Bar: class agreement >= 0.80 and Cohen's kappa >= 0.60, 95% CIs. Opus 5.5
spend cap $2.00. If it fails, Part B falls back to option A: agreement with an
unvalidated judge, kappa and CI reported, no headline claim, no further Part B
spend.