# Proxy support for the audit stage diagnosis: full run on the 89 known-stage cases

2026-11-15. Same rule, prompts, model settings and amendment as the 10-trace pilot (`Proxy-support-pilot-v1.md`,
amendment 1). Population: all 89 `cases_v2` cases with audit status ok (`population.json` sha `6b428744…`,
recorded before any call). Qwen3-235B generates the facts; Gemini 3.6 Flash checks them against the gold
supports; Haiku 5.5 labels the checkpoints. Cap $1.0; spend **$0.413679**.

## Sample and generation

89 cases (59 cohort, 30 injected), 85 instances. **8 of 89 produced no usable fact set** (9%): 3 invented a
source id (a document title, `WMOP`, `unit-000004`), 3 returned no facts, 2 left `source_ids` empty. Two
further traces failed on transport (connection error on all attempts) and were retried once with the same
prompt and succeeded. 81 traces carry facts; 256 proxy facts.

Two runner defects were found and fixed while reading the outputs, with no change to the frozen prompt or
population:
- The amendment-1 flat-map branch of the parser returned on the `support_sets` key instead of skipping it, so
  every flat-map output was recorded as failed. Fixed; 13 traces were recovered by re-parsing their logged
  attempts (no new calls).
- One trace with a 12-fact list hit the 2000-token label cap (`completion_tokens` 2000 on all attempts); its
  two checkpoints were re-labelled once at 4000 tokens.

## Proxy facts against the gold supports

**Match (equivalent) 204/256 = .797 [.742, .844]**, 95% Clopper-Pearson.

| verdict | facts | share |
| --- | ---: | ---: |
| equivalent | 204 | 79.7% |
| partial | 10 | 3.9% |
| unsupported | 38 | 14.8% |
| contradicted | 4 | 1.6% |

- **Unsupported (38)**: facts from documents outside the gold chain. The model is not told which document is
  gold, so true-looking facts from distractors are unsupported.
- **Partial (10)**: over-specification — the fact adds a relation or qualifier the gold passage does not state
  (e.g. a year attached to the wrong edition).
- **Contradicted (4)**: agent-attribution errors — "Sidney Peel" for Arthur Peel, "Union" for Confederate,
  and two Kerry/Edwards inversions in one trace.

## Stage diagnosis on proxy facts

| | pilot (10) | full (81 scored) |
| --- | --- | --- |
| facts matched | 33/40 = .825 [.672, .927] | 204/256 = .797 [.742, .844] |
| stage vs gold-based audit | 7/10 = .700 [.348, .933] | **62/81 = .765 [.658, .852]** |
| stage vs known stage | 7/10 = .700 [.348, .933] | 52/81 = .642 [.528, .746] |

The gold-based audit itself agrees with the known stage on **63/81** of the same traces.

| proxy stage \ gold-audit stage | extraction | transmission | sharding | aggregation |
| --- | ---: | ---: | ---: | ---: |
| extraction | 43 | 4 | 1 | 0 |
| transmission | 3 | 16 | 2 | 1 |
| sharding | 2 | 0 | 2 | 0 |
| aggregation | 5 | 1 | 0 | 1 |

**The proxy reproduces the audit's errors, not just its labels.** Of the 63 traces where the gold audit is
right, the proxy agrees with it on 49; of the 18 where the gold audit is wrong, the proxy reproduces the
error on 15 and gives the correct stage on 3. Its .765 agreement with the audit therefore measures imitation,
and its .642 agreement with the truth is the number that says the proxy is worse than the audit, not a
substitute for it.

Where the 19 disagreements come from, read from the fact sets and labels:

- **6 aggregation flips** (proxy aggregation, gold extraction/transmission): every proxy fact is present, so
  the audit names aggregation; the gold fact that is missing never entered the proxy's fact set.
- **7 extraction or sharding flips** (proxy extraction/sharding, gold transmission): proxy facts taken from
  distractor documents or merged relations are absent from the extraction pool or the source shard.
- **6 partial flips** (proxy transmission partial, gold extraction/sharding/aggregation): over-specified
  facts are only partly carried at the board, so the audit names transmission.

## 8c. 2x2 reconciliation

| | proxy correct (vs known) | proxy wrong (vs known) |
| --- | ---: | ---: |
| gold-audit correct (vs known) | 49 (agree) | 14 (disagree) |
| gold-audit wrong (vs known) | 3 (disagree) | 15: 13 identical wrong label (agree), 2 different wrong label (disagree) |

Agreement with the gold audit = 49 + 13 = **62/81**, not 64. Adding 49 and 15 assumes every case where both
labels are wrong carries the *same* wrong label; 2 of the 15 do not. Both are sharding-truth cases where the
gold audit names extraction and the proxy names aggregation (`2hop__128342_375952`, `3hop1__637555_339990_15538`).
The 2x2 against truth and the agreement against the audit are different quantities; 62 is the agreement count
computed directly on the two mapped stage labels.

## Consequence for the proxy-support question

Model-generated facts reproduce the audit's label most of the time but inherit its mistakes, so they cannot
stand in for gold facts in the diagnosis. Any use of proxy support must report its own accuracy against known
stages, not agreement with the audit: here the two are nearly the same number (63/81 vs 62/81) while the
proxy's own accuracy is 13 points lower than the audit's (52/81 vs 63/81).

## Projection

Measured $0.00465/trace, including retries and failures. The 608-trace main-table run would cost ≈ $2.83 and
would lose about 9% of traces to generation failure. **Not started.**

## Ledger

$90.008548 before steps 8b/9b + $0.413679 (8b) + $0.314875 (9b) = **$90.737102**. Calls in `calls.jsonl`.