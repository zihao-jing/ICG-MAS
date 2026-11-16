# A3: does the audit name the correct fact? (frozen before scoring)

2026-11-16. Scope: the 41 known-cause failures (30 injected, 11 deleted-fact); each has two runs (Qwen and Gemini audit, old rule). Zero model calls.

## Fact table

Built by `scripts/f39_fact_tables.py` (output `rebuttal/pilots/20261116_stage_naming/fact_tables.json`):
- Injected: the intended fact is the uncorrupted sentence (`original` in `20261113_injected_distortion/accepted.json`). Audit facts and carriers from the injection matcher ledger (`20261113_audit_diagnosis_89/matcher_run/calls.jsonl`, Qwen) and the attribution pilot (`20261115_b5_attribution_2x2/calls.jsonl`, Gemini).
- Deleted-fact: the intended fact is `plan.fact` in `20261115_injection_amendA3/results.json`. Audit facts from the matcher record; carriers from the A3 ledger (carried calls from `20261115_injection_amendA2/calls.jsonl` where logged there).
- Match: the audit fact with the highest content recall to the intended fact, which must reach 0.8 and be unique. A run with no such fact is excluded and the reason recorded. No fact is guessed.

## Named

- Deleted-fact runs: named if the matched fact is absent at both checkpoints (no carrier at extraction and none at board). A fact flagged as distorted is not a naming of a lost fact.
- Injected runs: named if the matched fact is distorted or absent at the board checkpoint, where the injection sits.

Reported: named / matched runs per backbone and population, with Wilson 95% intervals; excluded runs with reason. A looser count (any non-faithful status) is reported alongside for transparency only.

Reported on the 41 cases (82 runs), per backbone. The 89-case set is not scored under this rule.
