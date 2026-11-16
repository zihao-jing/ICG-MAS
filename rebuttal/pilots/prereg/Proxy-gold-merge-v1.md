# Proxy–gold matched-granularity rescore, v1 (frozen before any call)

2026-11-15. Cap **$1.00**. Sensitivity check beside the 62/81 full-population agreement and the 6/30
failure-enriched agreement. It changes one thing only: the proxy facts are merged onto the gold facts before the
stage is read, so the proxy side is counted at the gold granularity instead of its own.

## Population

The 30 failure-enriched MuSiQue traces of `20261115_q1_second_sample` (listed in its `build_manifest.json`),
`qwen235b` / `random_relay`, answers wrong. Their stored per-fact labels from that run are reused at $0.

## Instrument

The frozen equivalence prompt `proxy_support_equiv_prompt_v1.json`, Gemini 3.6 Flash, temperature 0, 3,000
tokens, one call per trace carrying all of that trace's proxy facts and its gold support. The prompt is the one
used in every proxy-support run. It has no separate agreement-validation entry; this rescore therefore uses a
frozen instrument and is reported as a sensitivity check, not as validated.

## Merge rule

- A proxy fact joins a gold fact when its verdict is `equivalent` and its `support_ids` names exactly one gold
  support. Several proxy facts may join the same gold fact.
- Every other proxy fact (partial, unsupported, contradicted, no single support id, or unparsed) stays a group of
  its own.
- Group status at a checkpoint: `present` if any constituent proxy fact is `present` there, else `partial` if any
  is `partial`, else `absent`.
- Trace stage: any group `absent` at extraction gives `extraction`; otherwise any group `absent` at board gives
  `transmission`; otherwise `aggregation`. This is the same rule as both sides of the 62/81 and 6/30 figures.
- Agreement: the proxy stage equals the gold stage from the stored labels, over traces where both resolve.

## Output

Per-trace table (gold stage, unmerged proxy stage, merged proxy stage, equivalent facts, groups), the agreement
rate with a Wilson 95% interval, and the spend against the cap. Reported beside 62/81 (89 known-stage cases,
stages on both sides) and 6/30 (this failure-enriched sample, unmerged).