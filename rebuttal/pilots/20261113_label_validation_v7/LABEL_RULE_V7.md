# V7 re-validation of the fixed fidelity prompt (rule frozen before any call)

Written 2026-11-13, before any V7 reference or Haiku call. The V6 fidelity
label failed (124/147 = 0.844, kappa 0.264); the cause is recorded in
`rebuttal/pilots/20261113_label_validation_v6/FIDELITY_FAIL_CAUSE.md` and the
fix is prompt v4 (`per_fact_prompt_v4.json`, sha256 `6d0a124d...`), which
changes fidelity guidance only. Because the prompt changed, this rule
revalidates all three labels on a fresh disjoint set. V5 and V6 stay on
record unchanged.

## Population

`rebuttal/results/batch1/expansion_stage2`: 800 MuSiQue instances at each of
gemma31b, gpt4omini and qwen235b. Exclude the 60 V5 instances, the 60 V6
instances, and the 30 E1 anchor instances. From the remainder, order by
`sha256('43|v7|'+instance)`, take **60 instances**, choose the model by
`sha256('43|v7|model|'+instance)`, and write both checkpoints (extraction,
board): **120 cases**. The instances were never used in V5, V6 or labeller
development. Population is frozen in `population_v7.json` and
`v7_build_manifest.json` before the first reference call.

## Reference and labeller

- Reference: Gemini 3.6 Flash, `v7_reference_prompt.json` (the same
  status/fidelity/unit-id schema as V6), 120 calls, cap **$2.00**.
  Reference labels frozen to `reference_labels_v7.json` before any Haiku
  call, hash recorded in `v7_reference_manifest.json`.
- Labeller under test: Claude Haiku 5.5, prompt **v4**, 120 calls, cap
  **$0.50**.

## Frozen pass rules

1. **Carrier (board):** per-fact carrier agreement (a fact matches when the
   labeller's units intersect the reference's, or both say absent) >= 0.80
   and Cohen kappa >= 0.60, the V5 rule.
2. **Presence (extraction):** binary carried agreement >= 0.85 and kappa
   >= 0.60.
3. **Fidelity (board, primary):** among facts both label carried, binary
   faithful agreement >= 0.85 and kappa >= 0.60. Extraction fidelity is
   secondary.
4. All three must pass before prompt v4 is used to replace any old column.
   A failure is diagnosed and fixed again on another fresh set, not used.

CIs: exact Clopper-Pearson for agreement; instance-cluster bootstrap for
kappa (seed 43, 10,000 draws). The reference is an LLM, not author ground
truth; a PASS is cross-model agreement on these 120 MuSiQue cases.