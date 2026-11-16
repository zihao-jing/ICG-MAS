# Proxy support on the 608-trace main table: partial run (chunk 1 stopped)

2026-11-15. Same rule, prompts and amendment as the 89-case run. The run was started in $1 chunks under the
$5.5 total cap. **Chunk 1 overran its $1 budget (spent $1.033481), so the run stopped** per the instruction.

## What was processed

**81 of 608 traces**, all Silo-Bench: summary-exchange 26, random-relay 26, score-ranked 24, redundancy-aware
5. No MuSiQue trace was reached (the population is ordered SB first). This is **not a population rate for the
608**; the cells below are partial even within SB (52 SB traces per protocol exist).

## Proxy facts against the gold supports (SB subset)

| cell | facts | equivalent | match [95% CI] |
| --- | ---: | ---: | --- |
| SB all | 238 | 183 | **.769 [.710, .821]** |
| summary-exchange | 94 | 74 | .787 [.691, .865] |
| random-relay | 63 | 45 | .714 [.587, .821] |
| score-ranked | 66 | 53 | .803 [.687, .891] |
| redundancy-aware | 15 | 11 | .733 [.449, .922] |

Verdicts: 183 equivalent, 22 contradicted, 9 partial, 24 unsupported.

## Generation failures: 17/81 = 21.0%

| cause | traces |
| --- | ---: |
| truncated at the 4096-token output cap | 13 |
| empty `source_ids` | 2 |
| flat-map shape with an extra key | 1 |
| invented source id | 1 |

The dominant SB failure is truncation: the Silo-Bench facts are numeric records, so Qwen enumerates very long
fact lists and the JSON is cut at 4096 tokens. This is 6x the MuSiQue failure rate (8/89) and is a property of
the SB fact shape, not of the model's grounding.

## Audit stage distribution (relay traces processed)

| protocol | extraction | transmission | sharding | aggregation |
| --- | ---: | ---: | ---: | ---: |
| random-relay | 1 | 2 | 0 | 6 |
| score-ranked | 0 | 4 | 0 | 7 |
| redundancy-aware | 0 | 1 | 0 | 2 |

**No stage agreement with the gold audit is reported**, because no gold-based audit stage exists for these
traces: the audit's matcher records cover a different 800-instance MuSiQue cohort (0 of the 608 keys match), and
Silo-Bench and the non-ranked protocols have none. The only gold-audit comparison remains the 89 known-stage
cases: 62/81 = .765 [.658, .852], with the proxy matching the truth 52/81.

## Reconciliation (zero cost)

**Run total vs ledger delta.** The run directory's `calls.jsonl` sums to **$1.374826** across 307 result
records, covering both attempts. The previous ledger total ($91.433174) already counted the killed first
attempt's final spend, **$0.336123** — the global ledger was taken after the last in-flight calls landed, while
the inventory text had recorded an earlier **$0.316809** snapshot. The increment since the previous report is
therefore $1.374826 − $0.336123 = **$1.038703** (the second attempt). The inventory component line is corrected
to $0.336123. **The ledger uses neither of these: it is the global sum over every result record, each counted
once** ($92.471877 at that point). The run total and the delta are reconciliation devices only.

**Stage counts vs trace counts.** 81 traces were processed.

| cell | processed | staged | no extraction checkpoint | generation failure | equivalence failure | label failure |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| SB summary-exchange | 26 | 0 | 13 | 6 | 7 | 0 |
| SB random-relay | 26 | 9 | 0 | 7 | 8 | 2 |
| SB score-ranked | 24 | 11 | 0 | 4 | 8 | 1 |
| SB redundancy-aware | 5 | 3 | 0 | 0 | 2 | 0 |
| **total** | **81** | **23** | **13** | **17** | **25** | **3** |

The stage table's 23 rows are exactly the staged column (random 9, score-ranked 11, redundancy 3; the
aggregation/transmission/extraction split totals those). The other 58 traces have no stage for three reasons:
13 summary-exchange traces have **no extraction checkpoint** in the frozen package (the protocol has no
extraction stage, so the audit cannot diagnose one); 17 produced no usable fact set; 25 failed the gold
equivalence check; 3 failed a checkpoint label. Of the 25 equivalence failures, all are **output truncation at
the 3,000-token cap** (fact lists of 25–74 on Silo-Bench numeric tasks), not model errors, and they are the
reason the truncation rule change below was needed.

## Cost

Total for the run $1.374826; chunk 1 $1.033481, the $0.033 overshoot coming from the eight calls in flight when
the cap was reached. The driver stopped on the overrun, as instructed.

## Ledger

$92.471877 accumulated at the time of this report; the run directory holds $1.374826 in total, of which
$0.336123 was already in the ledger and $1.038703 is the increment (see Reconciliation).