# Validation of the board-presence label on summary-exchange boards, v1 — frozen before any call

2026-11-15. Cap **$1.00** (API-equivalent, Opus price $4 / $20 per M tokens, as in `scripts/part_b_step2_cli.py`; CLI cost
recorded beside it). Purpose: the summary-exchange omission figure is built on the board-presence label. Validate that label
on summary-exchange boards before any rescoring.

## Label under test

The stored board-presence label of `rebuttal/pilots/20261113_sb_presence_full/results.json` (checkpoint `board`,
protocol `summary_exchange`, 156 boards, 1,160 labelled facts). Its prompt is `labeller_prompt.json` (sha256 in the manifest),
validated on Silo-Bench boards at agreement .915 and kappa .653 (`20261113_sb_presence_validation/report_v2.md`).
Omission = the label's status is **not "present"** (partial or absent). Binary: present vs not present.

## Reference

Claude Opus 5.5 (`claude-opus-5-5`) through the local `claude` CLI, headless (`claude -p`), run from an empty temporary
directory, all tools disabled, the frozen prompt `labeller_prompt.json` as the system prompt, the rendered board as the user
message (`scripts/per_fact_labeller.render`), JSON output parsed with `scripts/per_fact_labeller.parse`. Temperature is the CLI
default (not settable); one call per board.

## Sample

30 facts from the summary-exchange boards, stratified: 10 present, 10 partial, 10 absent (by the stored label). Drawn before
any call by ordering the facts on sha256(`summary-omission-v1|<key>|<fact_id>`) within each stratum; first 10 per stratum.
Reference labels are taken for the sampled facts only; other facts on the same board are not scored.

## Bars and statistics

- Agreement (present vs not present) with the reference: Wilson 95% interval.
- Cohen's kappa (binary): instance-cluster bootstrap 95% interval (percentile, 2,000 draws, seed 43; clusters = boards).
- Agreement also reported on three classes.
- **PASS** iff point agreement ≥ .80 and point kappa ≥ .60. The intervals are reported beside the verdict.
- If it passes, rescore summary vs relay omission with the validated label (relay boards from the same run). If it fails,
  report the failure and do not rescore.

## Calls and logging

One reference call per board that contains a sampled fact. Every call (intent and result, cost, CLI and API-equivalent)
is logged to `calls.jsonl`. Stops when the API-equivalent total would exceed $1.00.
