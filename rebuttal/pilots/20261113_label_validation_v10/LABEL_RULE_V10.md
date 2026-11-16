# V10 fidelity validation with a stronger labeller (rule frozen before any call)

Written 2026-11-13, before any V10 reference or Opus call. V7-V9 kept Claude
Haiku 5.5 as the labeller and failed strict fidelity on kappa in three fresh
sets (0.443, 0.349, 0.338); the cause is the faithful/partial boundary, which
the two models do not share. V10 keeps the **same V9 prompt text** in both
models and changes only the labeller under test to **Claude Opus 5.5**. The
reference stays **Gemini 3.6 Flash**, a different model. This is the reviewer's
option B. If V10 fails, work stops and the cause is reported before any further
change; the old fidelity column stays and is marked unvalidated.

## Bar (replaces the V7-V9 0.85 agreement rule)

Strict fidelity passes only if agreement >= **0.80** and Cohen kappa >= **0.60**,
each with a 95% CI. This is the reviewer's newest instruction and supersedes
the 0.85 used in V7-V9. Presence and carrier retain their V7-V9 bars.

## Population

Natural cases: `rebuttal/results/batch1/expansion_stage2` MuSiQue instances at
gemma31b, gpt4omini and qwen235b. Exclude the 60 instances used in each of V5,
V6, V7, V8 and V9, and the 30 E1 anchor instances. From the remainder, order by
`sha256('43|v10|'+instance)`, take **60 instances**, choose the model by
`sha256('43|v10|model|'+instance)`, and write both checkpoints: **120 natural
cases** (extraction and board).

Constructed distortions: from the same 60 instances, for each instance find a
critical fact that contains a number and a board unit that carries that number.
Replace that number in the unit with a different number and record
`{fact_id, unit_id, original, replacement}` as the planted ground truth. One
constructed board case per usable instance, targeting at least **30 distorted
facts**. The fact text is unchanged; only the checkpoint is corrupted. Natural
and constructed cases are reported separately.

Population and constructs are frozen in `population_v10.json` and
`v10_build_manifest.json` before the first reference call.

## Reference and labeller

- Reference: Gemini 3.6 Flash, `v10_reference_prompt.json` (V9 reference text
  unchanged), 150 calls (120 natural + 30 constructed), one pass. Reference
  labels freeze to `reference_labels_v10.json` before any Opus call; its hash
  is recorded in `v10_reference_manifest.json`.
- Labeller under test: **Claude Opus 5.5**, `anthropic/claude-opus-5.5`,
  `per_fact_prompt_v10.json` (V9 labeller text unchanged), temperature 0,
  max_tokens 1200, 150 calls.
- **Whole-run cap $5.00** across reference and Opus; every call logs intent and
  result with `cost_usd`. The manifest records the V9 labeller prompt hash
  (`per_fact_prompt_v9.json`, sha256 `f518c16a...`) owed from Gap 1.

## Metrics and pass rules

1. **Strict fidelity (primary):** among natural facts both label carried,
   binary faithful agreement >= 0.80 and kappa >= 0.60.
2. **Distorted vs not (secondary):** the same table reports the binary
   `fidelity == distorted` agreement and kappa, natural and constructed
   separately. It does not replace strict fidelity.
3. **Constructed distortions:** report the fraction of planted facts each model
   labels `distorted` (sensitivity), with exact Clopper-Pearson CIs, and the
   model-to-model agreement on `distorted` for the planted facts.
4. **Presence and carrier:** kept from V7-V9 as consistency checks.

CIs: exact Clopper-Pearson for agreement; instance-cluster bootstrap for kappa
(seed 43, 10,000 draws). The reference is an LLM, not author ground truth; a
PASS is cross-model agreement on these cases. Constructed distortions test
whether the labels detect a known corruption, not whether natural failures are
distributed like them.