# Silo-Bench proxy-support partial run under the v2 prompt (208 traces; no population rate)

2026-11-15. Rule `Proxy-support-pilot-v1.md` (sha `823f30f2...`) with amendment 1, caps `Proxy-support-caps-v1.json` (sha `2fad0404...`: facts 8,000, equivalence 8,000, labeller 8,192). Population: all 208 Silo-Bench main-table traces. Qwen3-235B generates the facts from the question and the source shards; Gemini 3.6 Flash checks them against the gold supports; Haiku 5.5 labels the extraction pool and the board. Spend **$2.795149**. Facts prompt `proxy_facts_prompt_v2.json`, the granularity fix (sha `3bc1bc05...`).

## Truncation

**6/208 traces = 2.9% [1.1%, 6.2%]** ended with a stage exhausting its attempts with the completion at its cap. The 2% stop rule: TRIGGERED — run should stop.

Generation failures: 8 (3.8%). Equivalence-call failures: 9.

Of the 8 generation failures, 5 were cut at the output cap and 3 are shape or source-id rejections by the frozen parser or normaliser (a bare fact object with no wrapper, a flat map whose entries repeat `fact_id`, source ids carrying `[agent-0][Document: ...]` decoration). By cell: random_relay 1, redundancy_aware_relay 3, score_ranked_relay 3, summary_exchange 1.

## Population equivalence against the gold supports

| cell | traces | generation failures | facts | equivalent | match [95% CI] | cluster CI |
| --- | ---: | ---: | ---: | ---: | --- | --- |
| random_relay | 52 | 1 | 380 | 377 | 99.2% [97.7%, 99.8%] | [98.3%, 100.0%] |
| redundancy_aware_relay | 52 | 3 | 370 | 366 | 98.9% [97.3%, 99.7%] | [97.8%, 99.7%] |
| score_ranked_relay | 52 | 3 | 428 | 417 | 97.4% [95.4%, 98.7%] | [94.0%, 99.7%] |
| summary_exchange | 52 | 1 | 390 | 388 | 99.5% [98.2%, 99.9%] | [98.7%, 100.0%] |
| **all** | 208 | 8 | 1568 | 1548 | **98.7% [98.0%, 99.2%]** | **[97.8%, 99.4%]** |

CP = Clopper-Pearson over facts; cluster = instance-cluster bootstrap, 2,000 draws, seed 43.

## Audit stage distribution

Relay traces with a valid fact set and both checkpoint labels: 148 of 156 traces with an extraction checkpoint.

| protocol | extraction | transmission | sharding | aggregation |
| --- | ---: | ---: | ---: | ---: |
| random_relay | 0 | 18 | 1 | 31 |
| redundancy_aware_relay | 0 | 19 | 0 | 30 |
| score_ranked_relay | 0 | 17 | 1 | 31 |

**Why extraction is zero.** Not a labelling defect, and not the checkpoint labels: they do contain extraction
gaps (44 facts absent and 275 partial across the extraction checkpoints). The zero comes from the frozen
re-attribution rule (`src/audit/sharding_check.py`): a trace diagnosed `extraction_omission` is re-labelled
`sharding` when the fact is also absent from its source agent's input shard, and `mixed_sharding_extraction`
(also counted as sharding) when only some are. In this population the raw diagnosis was `extraction_omission`
twice, and **both** failed the shard-presence check and became `sharding` — hence extraction 0, sharding 2. In
the MuSiQue run (v1 facts) the same rule left 20 of 24 raw extraction-omission traces in the extraction column.
The difference is fact granularity, not labelling: a coarse v2 fact built from an agent's shard is also not
found wholesale in that shard's text, so the presence rule returns absent and the trace moves to sharding. Read
the column as "extraction-attributed after sharding re-attribution".

**No stage agreement is reported for these traces.** Silo-Bench carries no gold audit stage: the audit's matcher records exist only for a MuSiQue cohort, so the table is a distribution of the proxy's own labels.

## Spend

Run directory total $2.795149 (all `calls.jsonl` result records).

## Line accounting against the $7.5 cap

| component | spend |
| --- | ---: |
| prior line spend | 3.586890 |
| **this run** | **2.795149** |
| **line total** | **6.382039** |
| **remaining** | **1.117961** |


## Chunks

Four chunks, each at or under $1 of actual spend: 0.915918, 0.922559, 0.901367, 0.055305. No overrun.

## The truncated traces

| trace | stage cut | shape |
| --- | --- | --- |
| `summary_exchange|III-25_n10` | facts | graph task, 10 agents |
| `random_relay|III-24_n10` | equivalence | graph edge list |
| `random_relay|III-25_n10` | facts | graph task |
| `score_ranked_relay|III-25_n10` | facts | graph task |
| `score_ranked_relay|III-27_n10` | facts | graph task |
| `redundancy_aware_relay|III-25_n10` | facts | graph task |

All six are `n10` traces of the two graph-task families (III-24, III-25, III-27); no `n5` trace and no
array-task trace truncated. The fixed prompt groups a record into one fact, but a 10-agent graph still yields
enough edges per record to overflow 8,000 tokens in these instances; the one equivalence cut followed a
fact list that itself nearly filled the cap.

**Status: no population rate is reported for Silo-Bench.** The truncation rate 6/208 = 2.9% triggered the
2% stop rule, so the equivalence figures above are a partial population measurement, **not a reportable
proxy-quality rate**, and Silo-Bench stays out of the population table. What can be said: on the traces that
completed, the proxy's facts were equivalent to the gold supports 98.7% of the time; that figure is not usable
as proxy quality for the reason in the next section.

## Why the 98.7% equivalence is not proxy quality

The v2 prompt groups each numeric or graph record into **one coarse fact**, and the gold support for a
Silo-Bench trace is the agent shard that holds that same record. A coarse fact is therefore checked against
text that contains the record almost verbatim: the gold check is close to a copy test, which is why equivalence
rises from .769 on the 81-trace v1 partial to .987 here. The number says the proxy's fact generator copies the
shards faithfully at record granularity; it does **not** say the proxy finds the facts a question needs, which is
what a population rate is supposed to measure. Any use of the Silo-Bench equivalence figure must carry that
qualification.

## Prompt version and comparison with MuSiQue

This population uses `proxy_facts_prompt_v2.json` (the granularity fix). The MuSiQue 400-trace population
rate uses `proxy_facts_prompt_v1.json` (one fact per element). **The two rates are not on the same facts
prompt and are not pooled or compared as if they were.** Any table that cites both must state the prompt
version per row; the difference in fact granularity changes what the gold check is scoring.

## Disclosed limitation: the 19-row check is not a truncation estimate

The 8e before/after check ran on 19 unique Silo-Bench rows (the draw held one row twice; disclosed in
`20261115_e8_granularity/report.md`). Its after arm had 0/19 truncated, but zero in 19 rows has a 95% upper
bound of 17.6%, so it cannot validate a <= 2% rate. The 19-row result is evidence that the prompt fix removes
the per-element enumeration (facts per trace 17.4 -> 5.6) and improves the gold check (.946 -> .991); it is
**not** evidence about the population truncation rate. That rate comes from this 208-trace run.
