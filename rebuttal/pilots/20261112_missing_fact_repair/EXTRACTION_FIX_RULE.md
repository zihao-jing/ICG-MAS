# Frozen extraction-fix rule

Written 2026-11-12 before any call for this pilot. The prompt hash is recorded
in `prompt_manifest.json` by the runner before the first call; the runner
refuses to freeze if `calls.jsonl` already exists.

## Why

The Stage 2 clean cohort's delivery check (`presence_check.md`) found 33 of 59
instances where the targeted fact is stated in the target agent's own context,
6 partial and 20 absent after a manual read of every case. The previous repair
pilot failed at delivery because it reused the general relay extraction prompt,
which does not know which claim the repair needs.

## Cohort

The 33 **present** instances from `presence.json` (`label == 'present'` after
the manual read), one trace per instance in the frozen model order
`gemma31b, gpt4omini, qwen235b`. Partial and absent instances are not called:
absent is a design finding, and partial is not evidence that the fact is
stated. This is the subset; the full 59 are reported in `presence_check.md`.

## Fix

One **targeted extraction** call per case, on the target agent's own context
only. The model is the trace's own model (the agent being repaired), max 3
units, temperature 0, 512 output tokens. The prompt is new and frozen here:

System:

```
You are a careful evidence locator.
You are given a question, a target claim, and a document.
Return up to 3 sentences copied verbatim from the document that state or
directly support the target claim.
Rules:
- Copy each sentence exactly as it appears; do not paraphrase, merge
  sentences, or add comments.
- A sentence must mention the entities in the claim and the relation the
  claim asserts.
- Output a numbered list, one sentence per line.
- If no sentence supports the claim, output exactly: NONE
```

User template:

```
Question: {question}

Target claim: {fact}

Document:
{target_agent_context}

Return up to 3 verbatim sentences from the document that state or directly
support the target claim.
```

This is an **oracle-targeted** repair: it uses the known missing claim, as the
repair arm in README section 6 does. It tests whether the agent's own context
contains the needed sentence and whether a targeted pass can deliver it.

## Delivery gate (unchanged)

`delivery_gate(' '.join(units), fact, question)` from
`src/audit/e4_fix_gates.py`: recall >= 0.8 and not a question, header, refusal
or data-list fragment. The delivery file is written and the outcome is not
read before it: the `--answers` step refuses to run without it. A blocked case
gets no repair answer.

## Arms and scoring

- **board-only control**: the original board, no repair, one answer call per
  case; frozen `_AGGREGATION_SYSTEM`; run after the delivery file exists.
- **repair**: original board plus up to 3 extracted units assigned to the
  target agent; called only for delivered cases.
- **scoring**: frozen exact `answer_f1 == 1.0` against the package gold answer
  (`src/eval/evaluate.answer_f1`); refusals are scored as wrong. No
  answer-equivalence check and no LLM judge are used here.

## Cost and stop

Hard cap **$5** for the pilot, all phases together; every intent and result is
appended to `calls.jsonl` with cost. If the cap is reached, remaining calls are
logged as skipped. Estimated spend is under $0.20 at list prices.