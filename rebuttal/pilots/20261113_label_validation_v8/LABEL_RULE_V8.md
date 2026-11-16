# V8 re-validation: one label definition in both prompts (rule frozen before any call)

Written 2026-11-13, before any V8 reference or Haiku call. The V7 fidelity
label failed on kappa (136/152 = 0.895, kappa 0.443); the cause is recorded in
`rebuttal/pilots/20261113_label_validation_v7/FIDELITY_FAIL_CAUSE_V7.md`.
Fourteen of the sixteen disagreements are the two prompts applying different
partial/fidelity definitions (explicit statement vs entailment; different
contradiction scope). V8 fixes the **reference prompt**, not the case design
and not the labeller: the reference receives the labeller prompt v4 verbatim,
with only the role sentence changed. Both models then apply one written
definition, so a PASS is cross-model reliability on that definition rather
than definition agreement. The reference is still an independent stronger
model. V5, V6 and V7 stay on record unchanged.

## Population

`rebuttal/results/batch1/expansion_stage2`: 800 MuSiQue instances at each of
gemma31b, gpt4omini and qwen235b. Exclude the 60 V5 instances, the 60 V6
instances, the 60 V7 instances, and the 30 E1 anchor instances. From the
remainder, order by `sha256('43|v8|'+instance)`, take **60 instances**, choose
the model by `sha256('43|v8|model|'+instance)`, and write both checkpoints
(extraction, board): **120 cases**. The instances were never used in V5, V6,
V7 or labeller development. Population is frozen in `population_v8.json` and
`v8_build_manifest.json` before the first reference call.

## Reference and labeller

- Reference: Gemini 3.6 Flash, `v8_reference_prompt.json` (the labeller prompt
  v4 text with the role sentence changed), 120 calls, cap **$2.00**. Reference
  labels freeze to `reference_labels_v8.json` before any Haiku call, hash
  recorded in `v8_reference_manifest.json`.
- Labeller under test: Claude Haiku 5.5, prompt **v4**, 120 calls, cap
  **$0.50**.

## Frozen pass rules

1. **Carrier (board):** V5 carrier match rate (unit intersection or both
   absent) >= 0.80; paired carrier-presence Cohen kappa >= 0.60.
2. **Presence (extraction):** binary carried agreement >= 0.85 and kappa
   >= 0.60.
3. **Fidelity (board, primary):** among facts both label carried, binary
   faithful agreement >= 0.85 and kappa >= 0.60. Extraction fidelity is
   secondary.
4. All three must pass before prompt v4 is used to replace any old column.
   A failure is diagnosed and fixed again on another fresh set, not used.

CIs: exact Clopper-Pearson for agreement; instance-cluster bootstrap for
kappa (seed 43, 10,000 draws). The reference is an LLM, not author ground
truth; a PASS is cross-model agreement on these 120 MuSiQue cases. The prompt
alignment is a deliberate fix after V7 and is stated wherever the V8 result
appears.