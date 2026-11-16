# B5: attribution comparison 2x2 (audit vs Who&When-style judge; Qwen vs Gemini)

2026-11-15. Frozen before any call of this step. Population: the **89 known-stage cases** already frozen in
`20261113_attribution_comparison/cases_v2.json` (30 injected distortions with known stage transmission; 59
cohort cases with known stage extraction 39 / sharding 20). Nothing about the cases changes.

## Cells

| row | column: Qwen-235B | column: Gemini 3.6 Flash |
| --- | --- | --- |
| audit, measured diagnosis | existing run `20261113_audit_diagnosis_89` (70/89) — **the earlier run, kept on record** | **new**: `matcher_v2.match_trace` with Gemini 3.6 Flash on every case, then `diagnose_with_sharding`, stage map as in the earlier run |
| Who&When-style judge | **new**: the frozen `attribution_prompt_v1.json` with Qwen-235B | existing run `20261113_attribution_comparison` (67/89) — the earlier run, kept on record |

Both new cells use the **same frozen prompts and parsers** as the earlier runs: `attribution_prompt_v1.json`
for the judge, `src/audit/matcher_v2.py` (facts + carriers, two structured calls per case) for the audit.
Only the model argument changes. Cohort cases run on the baseline package; injected cases on the corrupted
board built by `scripts/audit_diagnosis_89.py:corrupted` (the same construction the Qwen audit cell used).

## Validation of the Gemini-backed matcher, before the 2x2

The Gemini matcher is validated on **20 (model, instance) pairs disjoint from the 89 cases** — pairs that
have a frozen Qwen matcher record in `rebuttal/results/batch1/expansion_stage2/matcher/` and whose
(model, instance) does not appear in any of the 89 cases. Seed 44, sorted by
`sha256('44|b5val|model|instance')`.

- Reference: the **frozen Qwen matcher record's own diagnosis**, mapped to the audit stage vocabulary.
- Labeller: `match_trace` with Gemini 3.6 Flash on the same baseline package, then `diagnose_with_sharding`
  and the same map.
- Unit: one case, one five-class label (`extraction`, `sharding`, `transmission`, `aggregation`, `uncertain`).
- CIs: instance-cluster bootstrap, 2,000 draws, seed 43.
- **Bars: agreement >= .80 and Cohen's kappa >= .60.** If it fails, stop and diagnose; no 2x2 run without
  approval.

Cost: 20 cases x 2 Gemini calls, estimated $0.3. Cap **$0.5** for the validation.

## The 2x2 run

89 cases per new cell: 89 judge calls with Qwen, 89 cases x 2 matcher calls with Gemini. **Total cap $4.00**,
run in **chunks of $1 or less**; stop if a chunk's actual spend exceeds $1.00. Every call logged with intent
and result records. Model prices: Qwen $0.14/$0.80 per M, Gemini $0.75/$3.75 per M

## Transport adaptation (recorded before the scored calls)

The Gemini provider path rejects the OpenAI client's `response_format` parameter: through
`_get_client().chat.completions.create`, every variant (none, `json_object`, `json_schema`) returned a
connection error or empty content, while the project client (`single_request`, no `response_format`) returns
the object. The Gemini calls therefore go through `single_request` without `response_format`. Nothing in the
frozen matcher changes: the JSON schema is still in the system message that `match_trace` builds, and the
frozen strict parser plus `validate_facts`/`validate_carriers` still enforce it. Qwen calls use the client
path as the earlier audit run did. One transport test call was made before this note ($0.008070, logged in
`transport_test_calls.jsonl`).

## Scoring

- Per cell: stage accuracy against the known stage, Clopper-Pearson 95% CI.
- **Paired difference between backbones within each row**: the same cases scored by both backbones; paired
  bootstrap over cases (2,000 draws, seed 43) of (accuracy_Qwen - accuracy_Gemini), reported with its 95% CI.
- The earlier 89-case results stay on record and are cited as the earlier run; this report supersedes them
  only as the 2x2.

Four-model distortion rates are out of the headline (kappa lower bound below .40) and are not cited here.