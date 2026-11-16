# Silo-Bench two-step full run, amendment 1: facts-call cap

2026-11-15. Written before any call under this amendment. All other rules of
`Silo-Bench-two-step-full.md` stand unchanged, including the $4.00 cap, the 2% truncation stop,
the granularity bar and the exclusion of the six previously truncated traces.

## What happened

The run stopped at its own rule after 41 completed rows (20 reused pilot rows + 21 new): 1 trace
truncated, 1/41 = 2.4% > 2%.

That trace is `qwen235b|SB|results/run_qwen235b_n10|random_relay|III-25_n10`. Its selection call
picked all 10 rows, so the facts call had to emit coordinate arrays for 10 rows and hit the 8000-token
cap on attempts 1 and 2. Attempt 3 stopped after 697 tokens but returned its fact list as a dict keyed
`f1`..`f12` instead of a list, so validation rejected it. The trace has `facts: null`.

## Change

The facts call's token cap rises from 8000 to **16000** (`FACTS_TOK`) for every trace of this run.
The selection and equivalence caps stay at 800 and 8000. Truncation is still recorded per call at the
cap in force (16000 for facts), and the stop rule still applies to the cumulative truncated share.
Nothing else changes; no prompt text changes.

## Resume

The `III-25_n10` row is moved unchanged to `results_failed_attempt.jsonl` and re-run once under this
amendment. No other completed row is re-run. The six traces truncated in the earlier full-fact
extraction remain excluded at the instruction of the reviewer.

## Why this fix

The truncation came from a call whose output size scales with the number of selected rows, not from
a property of the trace's documents. Raising that one cap lets the same frozen prompt finish the same
job; it does not change which rows are selected or how facts are generated.