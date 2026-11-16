# Part B k = 1 manifest and answer rule (frozen before any call)

Date: 2026-11-14. Stage: aggregation answer on a k = 1 board rebuilt from the
stored extraction and scoring states of the E1 held-out runs. No judge call is
made under this rule; the manifest is frozen before any judge runs.

## Population

80 held-out E1 instances, three base models each (`qwen235b`, `gpt4omini`,
`gemma31b`), read from `results/<run>/results.json`,
`instance_results.score_ranked_relay[id].correct`. A trace is **wrong** when
`correct` is false. Run map, fixed here:

- MuSiQue: `run_qwen235b_musique`, `run_musique_gpt4omini`, `run_musique_gemma31b`.
- Silo-Bench n = 5: `run_qwen235b_n5`, `run_gpt4omini_n5`, `run_gemma31b_n5`.
- Silo-Bench n = 10: `run_qwen235b_n10`, `run_gpt4omini_n10`, `run_gemma31b_n10`.

Agent count n = hop count for MuSiQue (2, 3 or 4 from the id prefix), 5 or 10
for Silo-Bench as the run name says.

Order the wrong traces by `SHA-256(json([42, model, instance_id]))`. The first
**126** are the main-run traces; the next **30** are the validation traces. The
two sets are disjoint and fixed before any call.

## k = 1 board

Reconstruct the extraction and scoring states with
`reconstruct_states_and_scores` on `results/<run>/api_responses.jsonl`; apply
`get_transmitted_units(instance_id, 'score_ranked_relay', states, scores, n, k=1)`.
The board is every selected unit, `{unit_id: k1:a<a>:u<j>, agent_id, text}`.
The transmission checkpoint equals the board. Nothing is reselected by hand.

## Answer call

Prompt: `_AGGREGATION_SYSTEM` plus `_build_evidence_board_prompt` on the per-agent
k = 1 unit lists and the question. Model: the trace's own base model. Temperature
0, seed 42, max output 1,024. One SDK attempt per trace; no hidden retries.
The answer is stored with the rendered blind trace; correctness is recomputed
with the same matchers as the main table and recorded, but it does not change
the population.

## Manifest

For every trace: source run, model, instance, n, k = 1 board, SHA-256 of the
board, SHA-256 of the prompt, the answer text and its SHA-256. The manifest is
written and hashed before any judge call. Any later change needs a new,
separately hashed version.

## Budget and stop rules

156 calls, cap **$0.51** at the base-model prices in
`rebuttal/pilots/20261108_preflight/pricing.json`. Stop and report if the
running cost passes the cap or any call fails; a failed call blocks resume
until it is reviewed.

## Labellers (after the freeze, not in this run)

Part B judge: Gemini 3.6 Flash on the frozen k = 1 trace, prompt `E2_B` from
`rebuttal/judge/judge_prompts_v3.json`. Validation reference: Opus 5.5 on the
same 30 validation traces from the trace alone, same prompt, frozen before the
Gemini labels. Bar: class agreement >= 0.80 and Cohen's kappa >= 0.60 with 95%
CIs. If it fails, the judge is unvalidated for this label and only agreement is
reported.