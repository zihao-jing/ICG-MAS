# Proxy-vs-gold audit stage agreement (frozen before the comparison)

2026-11-15. No calls: both sides are computed from stored records. Cap $0.

## Question

On the same traces, does the audit name the same stage when it reads model-generated (proxy) facts as when it
reads the gold supports? The quantity is **agreement between the proxy-fact audit stage and the gold-fact audit
stage**. It is not accuracy against a true stage, and no true stage is claimed.

## Population

The three 30-trace UEGh Q1 samples, unchanged: sample 1 (uniform draw from the wrong-trace pool), sample 2
(enriched by whole-support lexical loss), sample 3 (enriched at atom level; it returned the same 30 traces as
sample 2). All are `random_relay` rows of the 400-trace MuSiQue Qwen run whose `score_ranked_relay` run is wrong;
that is the protocol the Q1 scripts selected, and the gold labels were taken from those same rows' checkpoints.

## Proxy stage

Per trace, from the stored proxy-support records (`20261115_proxy_support_mq`): the row's Qwen facts
(`facts.json`, status ok), the Haiku checkpoint labels for that row (`labels.json`,
`audit/<row key>/extraction` and `audit/<row key>/board`), assembled by `carriers_for` and passed to
`diagnose_with_sharding(..., correct=False)` exactly as in `proxy_mq_score.py`; the returned label is mapped
through `STAGE`. A trace with a failed fact set or a failed checkpoint label has no proxy stage and is excluded.

## Gold stage

From the stored Q1 labels, same derivation as the corrected Q1 scorer: statuses read from the dict value of each
checkpoint; any atom absent at extraction gives `extraction`; otherwise any atom absent at board gives
`transmission`; otherwise `aggregation`; partial counts as present. A trace with an empty checkpoint response has
no gold stage and is excluded.

## Agreement and interval

Agreement per sample = traces with proxy stage == gold stage / traces with both stages. Wilson 95% interval on
that proportion. The confusion table (proxy stage rows, gold stage columns) is reported beside the rate, and the
per-protocol proxy stage distribution recomputed here must reproduce the stored distribution for
`summary_exchange` before any row is reported.

## Caveats stated with the result

The same labeller (Haiku 5.5) labels both fact sets at the same two checkpoints, so shared labeller error inflates
agreement. The gold side's stage is itself an audit computation, not ground truth. Samples 2 and 3 select traces
by a lexical-loss filter, so their proxy-side stage distribution is not the population's.