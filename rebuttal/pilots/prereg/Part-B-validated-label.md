# Part B first-missing-checkpoint labels from the validated presence labeller

2026-11-15. Cap: within the approved $1.00 line, of which $0.603444 is spent; **$0.396556 remains**. No calls to
derive the labels: they are read from stored records.

## Labels

For each of the 89 Part B cases, the frozen Qwen facts, and each checkpoint, the presence status is read from the
stored design-A carrier records (`20261115_b5_qwen_design_a/calls.jsonl`, prompt v3 carrier schema). Fact status:
present if any faithful carrier, partial if only a partial carrier, absent if none. Validated at the board
(presence κ .857) and the extraction pool (κ .780); the Silo-Bench extraction point label (κ .847) is not used here.
A fact's first missing checkpoint: extraction if absent at extraction; else transmission if absent at board; else
aggregation. The sharding label remains the lexical input-presence check.

## Counts

Multi-stage = a case whose facts have more than one first-missing checkpoint; reported per population (cohort
natural failures, injected) and overall.

## Opus reference

A stratified sample of facts by derived stage, at most three per stage and at most seven facts in total (cost
projected per call against the remaining $0.396556, skipping any call that would exceed it). Opus 5.5 through the
CLI route only, the frozen stage prompt, JSON output. Agreement and Cohen's κ against the derived label; bars
.80 agreement and .60 κ.