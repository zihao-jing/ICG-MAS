# Amendment 1: gold side uses the frozen label parser

2026-11-15, before the comparison is reported. The Q1 label plates were found to contain checkpoint replies whose
atom keys do not match the trace's gold atom set (the renderer passed atom texts without ids). The gold stage here
uses a checkpoint only when it validates under `per_fact_points_run.parse`: the key set is exactly the gold atom
set, every status is present/partial/absent, and `unit_ids` is a list. A trace with fewer than two valid
checkpoints has no gold stage and is excluded.

Denominators in the result: `n_gold` is the number of traces with a gold stage; `n_both` is the number with both a
gold and a proxy stage, and it is the denominator of the agreement rate. `n_both` is smaller than `n_gold` when a
trace has no proxy stage.

Nothing else in the rule changes. The rule file is unchanged; this amendment is hashed with the report.
