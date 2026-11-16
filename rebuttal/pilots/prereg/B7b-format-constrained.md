# B7b: format-constrained confirmatory insertion rerun

2026-11-15. Pre-registered format fix. Frozen before any call. Cap **$1.50**, chunks of $1 or less.

## Why

B7 (same 59 insertion cases, Opus 5.5, frozen prompt) scored lower than the earlier run under the exact rule
(22/59 vs 32/59), and higher under the post-hoc containment counter (47/59 vs 40/59). The gap is answer
format: B7's Opus answers are sentences ("About 11,900 people.") scored against bare gold values ("11,900").
This rerun removes that confound **by changing the instruction only**, before seeing its results.

## Design

Same 59 cases, exact `control_board` / `insert_board` from
`20261112_missing_fact_repair/direct_insertion/cases.json`, Opus 5.5, temperature 0, `max_tokens=1024`, both
arms. The only change from B7 is the system instruction, frozen here and hashed:

`_AGGREGATION_SYSTEM` plus:

> For this run, output the answer value only: one line with exactly the answer span, in the form a gold
> answer would take (a name, a number, a date, or a short phrase), with no label, no prefix and no
> explanation. If the units are insufficient, output exactly: Insufficient information.

The user prompt is byte-identical to B7's (`_build_evidence_board_prompt` over the same board).

## Comparison

- Primary: B7b exact correctness per case, paired against **B7's exact result** on the same case (both Opus,
  same boards; only the instruction differs).
- Also reported: B7b insert minus B7b control (within-run insertion effect), counts with Clopper-Pearson
  95% intervals, and the split by presence label.
- The earlier frozen-rule run and the post-hoc alias secondary stay on record and labelled as they are;
  they are not replaced.

## Budget

118 Opus 5.5 calls, about $0.9 at $4/$20 per million tokens. Hard cap $1.50, call-level enforcement.