# MuSiQue proxy-support population rate (400 traces, amended caps)

2026-11-15. Rule `Proxy-support-pilot-v1.md` (sha `823f30f2...`) with amendment 1, caps `Proxy-support-caps-v1.json` (sha `2fad0404...`: facts 8,000, equivalence 8,000, labeller 8,192). Population: all 400 MuSiQue main-table traces. Qwen3-235B generates the facts from the question and the source shards; Gemini 3.6 Flash checks them against the gold supports; Haiku 5.5 labels the extraction pool and the board. Spend **$1.868198**.

## Truncation

**0/400 traces = 0.0% [0.0%, 0.9%]** ended with a stage exhausting its attempts with the completion at its cap. The 2% stop rule: not triggered.

Generation failures: 20 (5.0%). Equivalence-call failures: 20.

Of the 20 generation failures, 0 were cut at the output cap and 20 are shape or source-id rejections by the frozen parser or normaliser (a bare fact object with no wrapper, a flat map whose entries repeat `fact_id`, source ids carrying `[agent-0][Document: ...]` decoration). By cell: random_relay 4, redundancy_aware_relay 3, score_ranked_relay 4, summary_exchange 9.

## Population equivalence against the gold supports

| cell | traces | generation failures | facts | equivalent | match [95% CI] | cluster CI |
| --- | ---: | ---: | ---: | ---: | --- | --- |
| random_relay | 100 | 4 | 327 | 254 | 77.7% [72.8%, 82.1%] | [69.0%, 86.2%] |
| redundancy_aware_relay | 100 | 3 | 302 | 235 | 77.8% [72.7%, 82.4%] | [71.6%, 83.9%] |
| score_ranked_relay | 100 | 4 | 290 | 233 | 80.3% [75.3%, 84.8%] | [74.4%, 86.3%] |
| summary_exchange | 100 | 9 | 302 | 244 | 80.8% [75.9%, 85.1%] | [73.4%, 87.7%] |
| **all** | 400 | 20 | 1221 | 966 | **79.1% [76.7%, 81.4%]** | **[75.3%, 82.7%]** |

CP = Clopper-Pearson over facts; cluster = instance-cluster bootstrap, 2,000 draws, seed 43.

## Audit stage distribution

Relay traces with a valid fact set and both checkpoint labels: 289 of 300 traces with an extraction checkpoint.

| protocol | extraction | transmission | sharding | aggregation |
| --- | ---: | ---: | ---: | ---: |
| random_relay | 5 | 19 | 2 | 70 |
| redundancy_aware_relay | 7 | 18 | 1 | 71 |
| score_ranked_relay | 8 | 21 | 1 | 66 |

**No stage agreement is reported for these traces.** They carry no gold audit stage: the audit's matcher records cover a different 800-instance MuSiQue cohort (0 keys match), so the table is a distribution of the proxy's own labels.

## Spend

Run directory total $1.868198 (all `calls.jsonl` result records).

## Line accounting against the $7.5 cap

| component | spend |
| --- | ---: |
| prior line spend | 1.718692 |
| **this run** | **1.868198** |
| **line total** | **3.586890** |
| **remaining** | **3.913110** |


## Chunks

The driver was stopped once, when its chunk-1 bar was still `chunk + $0.01` instead of the instruction's
$1.00 of actual spend, and restarted with the $1.00 bar, resuming from `pipeline.jsonl`. Spend before the
restart 0.667409 (including the calls in flight at the stop, which are logged and were re-run: six traces
have a logged call but no result record), then 0.900239 and 0.300550. Each chunk at or under $1.
