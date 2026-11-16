# V6 label validation: presence at extraction, fidelity at relay (rule frozen before any call)

Written 2026-11-13, before any reference or Haiku call. Design copies the V5
carrier validation: an independent reference model labels first under a frozen
prompt; its labels are hashed before the labeller under test runs; both are
scored on held-out cases. The labeller under test is Claude Haiku 5.5 with the
frozen prompt v3 (the same prompt as V5). The reference is Gemini 3.6 Flash,
which differs from the labeller and from the assistant that wrote the rubric.

## Labels and stages

1. **Presence at the extraction checkpoint** - does the extraction pool carry
   each critical fact (`status` present/partial vs absent). Primary metric:
   binary carried (status != absent) agreement between the labeller and the
   reference.
2. **Fidelity at the relay checkpoints (extraction and shared board)** - for
   facts both label as carried, is the fact still correct. Primary metric:
   binary faithful (`fidelity == faithful`) agreement. The three-class
   confusion (faithful/partial/distorted) is reported descriptively.

The carrier/unit-id question is already validated by V5 and is not the target
here; unit ids are still requested so the reference labels are self-contained.

## Population and held-out split

`rebuttal/results/batch1/expansion_stage2`: 800 MuSiQue instances at each of
gemma31b, gpt4omini and qwen235b. Exclude the 60 V5 instances (`population_v5.json`)
and the 30 E1 anchor instances used in labeller development. From the
remaining pool, order by `sha256('43|v6|'+instance)` and take **60 instances**;
choose the model by `sha256('43|v6|model|'+instance)`. Write both checkpoints
(extraction, board) for each, giving **120 cases** and the audit matcher fact
list. These instances were never used in V5 or in labeller development.

Population written to `population_v6.json`, its sha256 and the prompt/system
sha256 frozen in `v6_build_manifest.json` before the first reference call.

## Runs and caps

1. Reference: Gemini 3.6 Flash, `v6_reference_prompt.json`, temperature 0,
   reasoning enabled, max_tokens 8192. 120 calls, cap **$2.00**. Every call
   logs intent and result to `reference_calls.jsonl`.
2. Freeze reference labels to `reference_labels_v6.json`, hash and record in
   `v6_reference_manifest.json` **before** the Haiku calls.
3. Labeller: Claude Haiku 5.5, prompt v3, temperature 0, max_tokens 2000.
   120 calls, cap **$0.50**. Call log `calls_v6.jsonl`.

No call is made before the rule, prompt, population and build manifest are
written and hashed.

## Frozen pass rules

- **Presence (extraction):** PASS only if binary agreement >= 0.85 and Cohen
  kappa >= 0.60 on the 120 extraction facts. Report the exact
  Clopper-Pearson 95% CI and an instance-cluster bootstrap kappa CI (seed 43,
  10,000 draws).
- **Fidelity (board, primary; extraction secondary):** among facts both label
  carried, PASS only if binary faithful agreement >= 0.85 and kappa >= 0.60.
- A label that fails is not used to replace an old column. The cause must be
  diagnosed (read the disagreements), the prompt fixed, and the fixed prompt
  re-validated on **fresh cases** (a disjoint instance set under a new frozen
  rule) before it is used.

## Caveats

The reference is an LLM applying a written prompt, not author ground truth.
A PASS is cross-model agreement on MuSiQue at these checkpoints, not
author-validated truth, and it does not cover other benchmarks or models.