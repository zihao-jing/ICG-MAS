# Labeller re-pilot, prompt v2

Canonical record for the v2 re-pilot. Run 2026-11-12. The run used 20 E1 dev traces, two authors each, all disjoint from the first 20-trace pilot and from the 150-trace validation set.

## Prompt identity

There are two different hashes, and they identify different things:

| what | sha256 | meaning |
| --- | --- | --- |
| prompt file, `labeller_prompt_v2.json` | `7f9e281669ca06e00eac86405312bb54c05cc69834eb51a732e48a669e8268c6` | sha256 of the JSON file bytes. **This is the frozen reference.** |
| system prompt text inside that file | `585d0d453ffceffe2372169ae7d312a2fbcab9d5854e241e96244f33dfdb8e6e` | sha256 of the `system` string only. This is the value recorded in every call log. |

The manifest `rebuttal/pilots/20261112_labeller/labeller_prompt_v2.manifest.json` records both, with the file hash as the reference. The runner's `load_prompt()` checks both before a call: the system string against `system_sha256`, and the file bytes against the manifest's `file_sha256`.

## Run record

- Model: `anthropic/claude-haiku-5.5` via OpenRouter, temperature 0, no reasoning.
- Traces: 20, two authors each (40 author comparisons).
- Prompt version: `v2`.
- Spend: **$0.011987** against the $0.25 cap.
- Every call is logged at `rebuttal/pilots/20261112_repilot_v2/repilot_calls.jsonl` (20 records, all successful, each with raw output, parsed output, usage, cost, prompt version and `system_sha256`).
- Manifest: `rebuttal/pilots/20261112_repilot_v2/repilot_20.jsonl`; meta: `rebuttal/pilots/20261112_repilot_v2/repilot_manifest_meta.json`.

The 20 traces were read from the E1 dev returns (`E1dev_A..D_labelling-v1.0.json`), grouped by `item_id`. The build asserted 20 rows, two authors each, and no overlap with `validation_150.jsonl` or `pilot_20.jsonl`.

## Per-trace labels

| # | trace | labeller | author A | author B | agrees |
| ---: | --- | --- | --- | --- | --- |
| 1 | Dev run 01 | DEFECT | CORRECT | CORRECT | no |
| 2 | Dev run 03 | DEFECT | DEFECT | DEFECT | yes |
| 3 | Dev run 05 | CORRECT | CORRECT | CORRECT | yes |
| 4 | Dev run 07 | DEFECT | DEFECT | DEFECT | yes |
| 5 | Dev run 08 | DEFECT | DEFECT | DEFECT | yes |
| 6 | Dev run 11 | CORRECT | CORRECT | CORRECT | yes |
| 7 | Dev run 12 | CORRECT | CORRECT | CORRECT | yes |
| 8 | Dev run 13 | CORRECT | CORRECT | CORRECT | yes |
| 9 | Dev run 14 | DEFECT | DEFECT | DEFECT | yes |
| 10 | Dev run 16 | DEFECT | DEFECT | DEFECT | yes |
| 11 | Dev run 19 | DEFECT | DEFECT | DEFECT | yes |
| 12 | Dev run 20 | DEFECT | DEFECT | DEFECT | yes |
| 13 | Dev run 02 | DEFECT | DEFECT | DEFECT | yes |
| 14 | Dev run 04 | CORRECT | CORRECT | CORRECT | yes |
| 15 | Dev run 06 | CORRECT | CORRECT | CORRECT | yes |
| 16 | Dev run 09 | CORRECT | CORRECT | CORRECT | yes |
| 17 | Dev run 10 | CORRECT | CORRECT | CORRECT | yes |
| 18 | Dev run 15 | DEFECT | DEFECT | DEFECT | yes |
| 19 | Dev run 17 | DEFECT | DEFECT | DEFECT | yes |
| 20 | Dev run 18 | CORRECT | CORRECT | CORRECT | yes |

All 20 calls parsed to a verdict. Strict single-object parsing succeeded on 19 of 20. `Dev run 01` emitted two JSON objects: a first verdict and then a correction. The declared rule is to use the last complete verdict object; the first was discarded. The final label for that trace is DEFECT.

## Agreement

- Raw agreement: **0.950** (38 of 40 author comparisons).
- Cohen's kappa: **0.900**.
- 95% CI, cluster bootstrap over the 20 item clusters (2,000 draws, seed 42): agreement **0.850-1.000**, kappa **0.667-1.000**.
- Disagreements: **1 trace**.

### Dev run 01

- Gold: `Nicholas Bacon`
- Answer: `Sir Nicholas Bacon`
- Exact token-F1: 0.800.
- Labeller: DEFECT — "The final answer 'Sir Nicholas Bacon' adds the word 'Sir' relative to the gold 'Nicholas Bacon', so the normalized token lists differ. The critical fact (Nicholas Bacon as father of Francis Bacon) is extracted at extraction:a0:u2 and passed to board:a0:u0 faithfully, so no pool or board checkpoint loses or distorts it."
- Authors: A=CORRECT, B=CORRECT.
- Direction: the labeller is stricter than the authors. This is the same honorific-prefix strictness the v1 pilot exposed; the v2 prompt did not remove it, and it is the one remaining error in an otherwise exact match.

## Caveat

The 20 dev traces are author-unanimous: both authors gave the same label on every trace. The 0.950/0.900 score therefore measures agreement with a single consensus label, not the labeller's ability to resolve author disagreement. The 150-trace validation set has 80 traces with two authors; only those can test disagreement resolution. The CIs are correspondingly wide (agreement lower bound 0.850, kappa lower bound 0.667), and the one disagreement is a systematic strictness case, not random noise.

## Go / no-go

Requirement: lower CI bound at least 0.80 agreement and kappa at least 0.60. **Passed** (0.850 and 0.667). The full 150-trace run was approved on 2026-11-12 after this re-pilot was reviewed.

## Full 150-trace run

Completed later on 2026-11-12: 150/150 parsed (4 traces retried at 2,000 output tokens), spend $0.114821, agreement **0.953** (95% CI 0.913-0.987), kappa **0.878** (95% CI 0.760-0.965), 7 labeller-vs-author disagreements. The 150 traces are also author-unanimous, so this run does not test author disagreement either. Detail and the per-trace disagreement list: `rebuttal/pilots/20261112_labeller_v2_full/full_report.md`.