# Answer-equivalence check: rule, validation and go/no-go

Written and frozen 2026-11-12, **before any call**. This replaces the withdrawn
plan to re-score the main tables with the v2 evidence-flow labeller.

## What the check is

`answer_equiv_v1.json` (model `anthropic/claude-haiku-5.5`, OpenRouter,
temperature 0). Input: question, gold answer, system final answer. Output: one
JSON object, `verdict` = `EQUIVALENT` or `NOT_EQUIVALENT`. It judges only
whether the two texts name the same thing; it says nothing about evidence flow.

The check does **not** replace the lexical rule by fiat. It is validated first,
against the 150 traces whose two authors agree on the binary call (`correct` =
answer correct, every other category = wrong answer). The author label is the
answer-correctness ground truth: `CORRECT` maps to `EQUIVALENT`, `DEFECT` to
`NOT_EQUIVALENT`.

## Validation set and spend

- 150 author-labelled traces (`rebuttal/pilots/20261112_labeller/validation_150.jsonl`):
  38 author-CORRECT, 112 author-DEFECT.
- One call per trace, retried once at a larger output budget if unparsed;
  every attempted call logged.
- Cluster = instance (the same instance can appear at several run lengths).
- 95% CIs by cluster bootstrap, 2,000 draws, seed 42.
- Cap **$0.50** for validation.

## Go/no-go (set before the run)

Run the 608-trace main-table check only if all three hold on the 150:

1. agreement with the author answer-correctness call >= **0.90**;
2. Cohen's kappa >= **0.75**;
3. EQUIVALENT recall on the 38 author-CORRECT traces >= **0.85** (the check
   must not erase correct answers).

If any fails, the check is reported as failed, the main tables keep the lexical
cells, and no 608-trace run starts.

## Main-table run (only if the gate passes)

- Same 608 traces as the v2 pilot: Qwen-235B, SB 52 + MQ 100, four protocols
  with a trace package. Case list: `rebuttal/pilots/20261112_rescore/cases.jsonl`.
- Per-cell answer-equivalence accuracy beside the lexical rule and the paper's
  original cells; the v2 evidence-flow rate is reported in its own column as a
  label, not as accuracy.
- Agreements and disagreements are listed per cell; every disagreement is
  checked against the answer text.
- Cap **$2.00**; every call logged. Original numbers stay on record.