# B7c: bare-value format with the earlier model

2026-11-15. Frozen before any call. Cap **$1.00**, chunks of $1 or less.

## Why

B7b changed two things relative to the original direct-insertion run: the model (trace's own -> Opus 5.5) and
the format (sentence prompt -> bare-value instruction). This arm holds the format fixed at bare value and
returns the model to the **trace's own** (the model of the original run), so the model effect and the format
effect can be separated.

## Design

Same 59 cases, `control_board` / `insert_board`, and inserted facts from
`20261112_missing_fact_repair/direct_insertion/cases.json`; the case's own model (`google/gemma-4-31b-it`,
`openai/gpt-4o-mini`, `qwen/qwen3-235b-a22b-2507`) in both arms; temperature 0; `max_tokens=1024`.

System instruction is the same frozen bare-value note as B7b (sha recorded), appended to
`_AGGREGATION_SYSTEM`; the user prompt is byte-identical to the original run's.

## Comparison, all paired per case

- B7c insert vs the original run's insert (32/59): the **format effect** for the earlier model.
- B7c insert vs B7b insert (Opus, bare value): the **model effect** at bare format.
- B7b insert vs B7 insert (Opus, sentence format): the format effect for Opus (computed from stored runs).
- B7 insert vs the original run's insert: the model effect at sentence format (stored runs).
- Also B7c insert vs B7c control within the run.

Counts with Clopper-Pearson 95% intervals; paired differences with a case bootstrap (2,000 draws, seed 43).

## Status of earlier results

The original 32/59 run and B7's sentence-format 22/59 stay on record; B7's post-hoc containment secondary
stays labelled post-hoc and is not used here.