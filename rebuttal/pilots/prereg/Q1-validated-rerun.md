# Q1 rerun with the validated renderer (frozen before any call)

2026-11-15. Cap **$0.50**. The Q1 labels passed atom texts without ids; the validated renderer passes `a1: text`.
This run re-labels both the gold supports and the proxy facts on the 31 unique traces with the validated renderer,
so the whole population is scored and the parser filter is no longer needed.

## Population

The 31 unique `random_relay` traces of the three Q1 samples (instances whose `score_ranked_relay` run is wrong),
taken from the 400-trace MuSiQue Qwen run. Per sample, the same 30 traces as before.

## Gold side

The first gold support of the row. Atoms: the support text split on `. `, parts longer than 3 characters. One call
labels all atoms of that support against one checkpoint (extraction, then board).

## Proxy side

The Qwen proxy facts of the row (`facts.json`, status ok). Atoms: each fact's text split the same way. One call per
fact and checkpoint.

## Renderer and labeller

Exactly `per_fact_points_run.render`: prompt `per_fact_points_prompt_v1.json` (system sha `86d84ff6…`), atom lines
`a1: <text>`, entries `[unit_id] (agent N) <text>` truncated to 1,500 characters, Claude Haiku 5.5,
temperature 0, max 4,096 output tokens. A reply is valid only if `per_fact_points_run.parse` returns labels for
exactly the atom ids sent; invalid replies get one retry, then the trace has no stage for that side.

## Stages and agreement

Gold stage: any gold atom absent at extraction gives `extraction`; otherwise any absent at board gives
`transmission`; otherwise `aggregation`. Proxy stage: the same rule over the proxy facts' atoms. Agreement per
sample = traces with both stages and the same stage / traces with both stages, Wilson 95% interval, confusion
table, reported beside the filtered legacy result.

## Budget

About 62 gold calls and 144 proxy calls at ~$0.0003 each, projected under $0.10. Hard cap $0.50 with per-call
projection and a skip record at the cap.