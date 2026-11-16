# B6: audit-guided repairs on the 59 missing-fact cases

2026-11-15. Frozen before any call. Cap **$5.00**, chunks of $1 or less, every call logged.

## Population

The 59 cohort cases of the 89-case attribution set (`cases_v2.json`, population `cohort`): 39 whose audit stage
is **extraction** and 20 whose audit stage is **sharding**. Each case carries the audit's per-fact detail
(`audit_diagnosis_89/audit_results.json`): the flagged fact id, its status, and its source agent shards.

## What is repaired, and where

One procedure, two named targets. The audit's flagged slot is the only input:

- **Extraction cases (39):** the fact exists in the agent's own source shard but the extraction pool missed it.
  The repair re-extracts from **that agent's own source shard text** with the frozen relay extraction prompt,
  delivering up to 3 units, so the pipeline stage named is **extraction**.
- **Sharding cases (20):** the fact is absent from the agent's input shard. The repair re-routes the **source
  support passage** for the flagged fact through the same extraction step so the owning agent now carries it
  on the board; the pipeline stage named is the **re-routed sharding stage**.

No oracle text: the context is the original source shard/support passage. The gold answer, the reference
answer, the final answer and the audit's own diagnosis text are never shown to the model. Delivery is gated by
the frozen `delivery_gate`; undelivered extractions never reach the board and that case is scored on its
original answer.

## Calls (two per repaired case at most)

1. Extraction: frozen `_EXTRACTION_SYSTEM` + `_build_extraction_prompt`, the trace's own model, temperature 0,
   512 tokens, up to 3 units.
2. Answer: frozen `_AGGREGATION_SYSTEM` + `_build_evidence_board_prompt` over the original board plus the
   delivered units, the trace's own model, temperature 0, 1,024 tokens.
Only run for cases whose delivered units pass the gate.

## Pairing and scoring

The original arm is the same trace's stored baseline prediction, zero cost. Both arms are scored with the same
function on the same instance: `answer_f1` against the gold answer, correct iff F1 = 1.0.

- Per cell (extraction, sharding) and overall: repaired minus original, paired by case.
- Binary correctness difference and mean-F1 difference, each with a 95% paired bootstrap CI over cases
  (2,000 draws, seed 43).
- The number of cases where the gate delivered nothing is reported separately; those cases are listed, not
  dropped.

## What this cannot show

A repair that adds the fact the audit flagged is a single-slot intervention. It cannot separate "the audit
picked the right slot" from "any correct fact added would have helped"; the report states this and reports the
per-cell counts so the reader can see the size of the intervention.