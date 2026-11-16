# V9 re-validation: boundary procedure in both prompts (rule frozen before any call)

Written 2026-11-13, before any V9 reference or Haiku call. V8 used the same
prompt in both models and still failed fidelity on kappa (143/156 = 0.917,
kappa 0.349); the cause is recorded in
`rebuttal/pilots/20261113_label_validation_v8/FIDELITY_FAIL_CAUSE_V8.md`.
Eleven of thirteen disagreements are the same boundary: the labeller requires
a relation or qualifier to be stated explicitly, while the reference credits
ordinary entailment. V9 keeps the label target and the three classes, and adds
one explicit boundary procedure to **both** prompts, verbatim: worked
entailment cases, a rule that a missing date/nationality/role/title is
incidental unless the question asks for it, and a restatement of the
contradiction rule with the Notus example. The reference and labeller still
receive identical text except for the role sentence. V5-V8 stay on record
unchanged.

## Population

`rebuttal/results/batch1/expansion_stage2`: 800 MuSiQue instances at each of
gemma31b, gpt4omini and qwen235b. Exclude the 60 instances used in each of V5,
V6, V7 and V8, and the 30 E1 anchor instances. From the remainder, order by
`sha256('43|v9|'+instance)`, take **60 instances**, choose the model by
`sha256('43|v9|model|'+instance)`, and write both checkpoints (extraction,
board): **120 cases**. The instances were never used in V5-V8 or labeller
development. Population is frozen in `population_v9.json` and
`v9_build_manifest.json` before the first reference call.

## Reference and labeller

- Reference: Gemini 3.6 Flash, `v9_reference_prompt.json`, 120 calls, cap
  **$2.00**. Reference labels freeze to `reference_labels_v9.json` before any
  Haiku call, hash recorded in `v9_reference_manifest.json`.
- Labeller under test: Claude Haiku 5.5, prompt **v9** (the same text), 120
  calls, cap **$0.50**.

## Frozen pass rules

1. **Carrier (board):** V5 carrier match rate (unit intersection or both
   absent) >= 0.80; paired carrier-presence Cohen kappa >= 0.60.
2. **Presence (extraction):** binary carried agreement >= 0.85 and kappa
   >= 0.60.
3. **Fidelity (board, primary):** among facts both label carried, binary
   faithful agreement >= 0.85 and kappa >= 0.60. Extraction fidelity is
   secondary.
4. All three must pass before prompt v9 is used to replace any old column.
   A failure is diagnosed and fixed again on another fresh set, not used.

CIs: exact Clopper-Pearson for agreement; instance-cluster bootstrap for
kappa (seed 43, 10,000 draws). The reference is an LLM, not author ground
truth; a PASS is cross-model agreement on these 120 MuSiQue cases. V9's
prompt sharpening is a deliberate fix after V8 and is stated wherever the V9
result appears.