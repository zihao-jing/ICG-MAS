# Q1 second sample (frozen before any call)

2026-11-15. Cap **$0.50**. A failure-enriched sample disjoint from the 31 traces already labelled, using the same
validated instrument on both sides.

## Population

The 68 wrong-instance `random_relay` rows of the 400-trace MuSiQue Qwen run. Excluded: the 31 instances used by the
three Q1 samples (union of their id lists). From the remaining 37, keep the traces where at least one gold atom
fails the lexical recall test at the extraction pool or the board (same atom test as sample 3), in population
order, and take the first 30. Every included trace is printed in the build manifest.

## Labelling

Identical to `Q1-validated-rerun.md`: Claude Haiku 5.5, prompt `per_fact_points_prompt_v1.json`, atom lines
`a1: text`, entries `[unit_id] (agent N) text[:1500]`, one call per fact and checkpoint, gold support as the single
gold fact, `per_fact_points_run.parse` for validation, one retry, cap projections per call.

## Stages and agreement

Any gold atom absent at extraction gives `extraction`; otherwise any absent at board gives `transmission`;
otherwise `aggregation`. Proxy stage over the proxy facts' atoms by the same rule. Agreement = same stage over
traces with both stages, Wilson 95% interval, confusion table. Reported separately from the first three samples.

## Budget

About 2 gold calls per trace and 2 × facts proxy calls, projected under $0.10; hard cap $0.50.