# Distortion-confirmer validation rule (frozen before any call)

Written 2026-11-13, before any reference call. This file is the design for
validating the distortion confirmer used in `results.json` of
`rebuttal/pilots/20261113_restore_source/`. It does not change that run; the
pilot and full reports stay on record.

## Object being validated

The confirmer is **Claude Haiku 5.5**, `anthropic/claude-haiku-5.5`, with the
frozen system prompt in `scripts/restore_source_pilot.py` (`CONFIRM_SYSTEM`)
and temperature 0. For each case it answers `source_states_fact` (yes/no) and
`board_contradicts` (yes/no). The run's `confirmed` gate is
`source_states_fact == yes` AND a mechanical verbatim-substring test of the
candidate source sentence in the source shard. The 132 figure is that gate's
count on all 184 cases. The confirmer has not been validated for the
`source_states_fact` judgement.

## Reference model and prompt

- Reference labeller: **Gemini 3.6 Flash**, `google/gemini-3.6-flash`
  (OpenRouter), temperature 0, reasoning enabled as the API requires.
- Reference prompt: `confirmer_reference_prompt.json`, a frozen copy of the
  confirmer's `CONFIRM_SYSTEM` text, so the only difference between the two
  calls is the model. The user text is the same `confirm_user(c)` render as
  the Haiku call (question, critical fact, candidate source sentence, board
  entry); the final answer is not shown.
- Reference output: strict JSON with the same two fields; parsed with the
  same `last_object` parser. Unparsed calls are retried at 8192 max tokens.
- The reference model differs from the confirmer and from the assistant that
  wrote the prompt. It is the stronger of the two models by
  parameter/price tier and is the same independent reference used for V5.

## Population and held-out split

The 184 unique distortion cases in `cases.json` (sha256 recorded in
`run_manifest_full.json`). The confirmer was first exercised and reported on
the pilot's first 40 cases (`load_cases()[:40]`, key order). Those 40 are
**development cases**. The held-out population is the remaining **144
cases**, written before the run to `confirmer_cases.json` (question, fact,
candidate source sentence, board entry, verbatim flag, Haiku answer) with its
sha256 frozen in `confirmer_manifest.json` before the first reference call.
No case was selected on its content or its Haiku label.

## Frozen analysis

1. **Primary agreement:** `source_states_fact` (yes/no) between Haiku and the
   Gemini reference on the 144 held-out cases. Report accuracy with an exact
   Clopper-Pearson 95% CI and Cohen kappa with an instance-cluster bootstrap
   95% CI (seed 43, 10,000 draws).
2. **Pass rule (frozen before the run):** PASS only if agreement >= 0.85 and
   kappa >= 0.60. Otherwise FAIL.
3. **Direction:** report the confusion matrix and every disagreement by type
   (`reference yes / confirmer no`, `reference no / confirmer yes`).
4. **Gate effect:** report the gate count on the held-out 144 under
   (a) the confirmer (`source_states_fact == yes` AND verbatim) and (b) the
   reference (`reference yes` AND the same mechanical verbatim flag). The
   verbatim flag is deterministic and unchanged; only the semantic call
   differs.
5. **Caveat:** the reference is an LLM, not author ground truth. A PASS
   validates agreement with that reference on these 144 cases, not the truth
   of the 132 count on all 184. A FAIL leaves the confirmer unvalidated and
   the 132 figure labeller-gated.

## Cost and logging

Cap **$2.00** for the whole reference run (144 calls; V5's 60 reference calls
cost $0.365430). A smoke call is made first at a $0.20 cap; if it parses and
costs in line, the remaining calls run under the same $2.00 cap. Every call
logs an intent record before dispatch and a result record with `cost_usd` to
`reference_calls.jsonl`. No call is made before the rule, prompt, population
and manifest are written and hashed.