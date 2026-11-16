# Frozen-prompt repair study

## Exact-span repair status (September 2026)

The earlier whole-source augmentation runs are exploratory and do **not** implement exact missing-piece restoration. The current runner now requires each evidence-gap repair to specify a manually verified, literal source span with `text`, `source_context_id`, and `verified_by`; it refuses an empty `missing_facts` list. On aggregation-gap cases it no longer appends source material. The six-case exact-span run is reported below.

The 20 audit candidates have now been reviewed in [`exact_span_review/casebook.md`](exact_span_review/casebook.md): six have recorded source excerpts for missing or distorted evidence, while 14 already have the needed raw data on the board and are reclassified as aggregation gaps. The validated per-setting decisions are in [`exact_span_decisions/`](exact_span_decisions/). The audit's `crit_recall` was computed from whole-shard or whole-paragraph overlap and did not identify atomic missing spans. Gemma's five-agent failures retain their aggregation-gap classification as requested. [`exact_span_review/gemma_n5_failures.jsonl`](exact_span_review/gemma_n5_failures.jsonl) remains an optional audit diagnostic.

The six-case evidence-only run is recorded in [`results/exact_span_evidence_20260926/summary.md`](results/exact_span_evidence_20260926/summary.md). The 14 reclassified cases are excluded. All 12 network retry calls succeeded; restoration made one of six answers correct versus zero of six in the saved original run. The initial sandboxed attempts failed with connection errors and are retained separately for audit.

The completed all-case aggregation stage-swap comparison is in [`results/aggregation_stage_swap_20260926/summary.md`](results/aggregation_stage_swap_20260926/summary.md). It includes all 326 revised aggregation-gap cases and compares the archived Gemini-terminal arm against a new one-agent Gemini-middle arm. The frozen cohort and call plan are in [`plan.md`](results/aggregation_stage_swap_20260926/plan.md) and [`cohort.csv`](results/aggregation_stage_swap_20260926/cohort.csv).

Three labeled evidence cases contain incorrect board summaries as well as the cited source excerpts. The `restored_fact` arm appends 11 source-verified correction notes that identify and correct the old values; the original units remain in the board. See [`exact_span_review/README.md`](exact_span_review/README.md) for the annotation details.

## Historical three-model run

The historical comparison uses Qwen-235B, GPT-4o-mini, and Gemma 4 31B as baseline models, with Gemini 3.6 Flash as the model intervention. It covers Silo-Bench with five and ten agents and MuSiQue. Model upgrade and whole-source augmentation were run on every selected failure case. The exploratory combined report is [`results/three_model_summary/summary.md`](results/three_model_summary/summary.md); machine-readable outputs are `combined_results.json`, `crossover_comparisons.csv`, `paired_comparisons.csv`, and `arm_scores.csv` in the same directory. All 456 cases in these three baselines have successful API responses for every historical arm (1,120 result rows). Gemma's ten-agent setting was completed in two nonoverlapping initial batches.

The user's case review was recorded as a global attestation in [`all_run_decisions`](all_run_decisions/), rather than individual semantic notes. The original `*_decisions.jsonl` templates below remain untouched. Mistral Small 4 was stopped after repeated upstream rate-limit errors at the user's request; its incomplete attempts under `results/mistrals_*` are excluded from the combined report. The other unsuccessful setup attempts under `results/` are also excluded. See [`results/README.md`](results/README.md) for the exact included directories.

The frozen manifests in this folder were reconstructed from cached score-ranked-relay runs. No API calls were made to create them. The `audit_hint` field is a coarse overlap proxy, **not** a verified atomic diagnosis. The historical `all_run_decisions` files record global case acceptance but no exact missing spans. Update decision files after reviewing the original shard, extracted units, transmitted board, and answer; leave the frozen manifests unchanged.

## Prepared model replication

The frozen-prompt study was prepared for four baseline models. Each model has 26 Silo-Bench five-agent cases, 26 Silo-Bench ten-agent cases, and 100 MuSiQue cases. The MuSiQue cases include 50 two-hop, 35 three-hop, and 15 four-hop questions. Every model/setting has its own `*_review.jsonl` manifest and `*_decisions.jsonl` sheet. Mistral is excluded from the completed comparison.

| Baseline model | File prefix | Silo-Bench five-agent cache | Silo-Bench ten-agent cache | MuSiQue cache |
| --- | --- | --- | --- | --- |
| `qwen/qwen3-235b-a22b-2507` | `qwen235b` | `run_qwen235b_n5` | `run_qwen235b_n10` | `run_qwen235b_musique` |
| `openai/gpt-4o-mini` | `gpt4omini` | `run_gpt4omini_n5` | `run_gpt4omini_n10` | `run_musique_gpt4omini` |
| `google/gemma-4-31b-it` | `gemma31b` | `run_gemma31b_n5` | `run_gemma31b_n10` | `run_musique_gemma31b` |
| `mistralai/mistral-small-2603` | `mistrals` | `run_mistrals` | `run_mistrals_n10` | `run_musique_mistrals` |

The extra models use the same score-ranked-relay protocol and the saved original model for exact replay, restored-fact, and noncritical-control arms. The aggregation comparator is preselected as `google/gemini-3.6-flash` in every `*_decisions.jsonl` sheet; this field alone does not assign a diagnosis or authorize an API call. Google lists this as a [stable model](https://ai.google.dev/gemini-api/docs/models/gemini-3.6-flash), and [OpenRouter lists](https://openrouter.ai/google/gemini-3.6-flash) standard rates of $0.75 per million input tokens and $3.75 per million output tokens as of September 2026. Its superiority on these frozen boards is a hypothesis to test. Report each baseline model and agent-count setting separately; the summary includes `source_id`, `original_model`, and `n_agents` for this purpose. Recheck model availability and pricing before API execution.

The runner is [`scripts/run_frozen_repair.py`](../../../scripts/run_frozen_repair.py). It uses the original relay system and user prompts for every arm, with the saved model, provider, output-token cap, and the original request's default temperature of 0.7. The original API logs contain responses but not the sent request text, so the prompt is reconstructed from the rollout code and locked with `original_prompt_sha256`.

## Review fields

For each retained record, set `reviewed_by` and `review_note`, then choose one diagnosis:

- `evidence_gap`: a necessary fact is absent or distorted on the board. Set `missing_facts` to the exact source span or spans, each with `text`, `source_context_id`, and `verified_by`. Each span must occur verbatim in the cited source context; for MuSiQue it must also occur in a gold supporting paragraph. For distorted derived summaries, `board_corrections` cites the old board unit and a value recalculated from its source list; the correction is appended as an additional board unit. The runner rejects empty `missing_facts`. A source-grounded noncritical `volume_control` of comparable length is optional. Silo-Bench does not annotate minimal atomic spans; its gold answer and full agent shards do not identify the exact missing piece.
- `aggregation_gap`: the existing board has all answer-critical facts faithfully expressed, but the answer is wrong. Keep the preselected `stronger_model` in the decision sheet. Do not add facts.
- `baseline_correct`: include as a stability control if desired. Its only new arm is an exact replay.
- `exclude`: insufficiently supported diagnosis; the runner skips this record before making a plan or API call.

Mark records that cannot be diagnosed confidently as `exclude`; do not relabel them based on a repair outcome. For Silo-Bench, prepare both five- and ten-agent sheets; MuSiQue has one sheet. Freeze the evaluation sample **before** observing new responses.

## Arms and comparisons

All reviewed records receive `exact_replay`: the original model, board, prompt, temperature, and token cap. Evidence-gap records receive `restored_fact`, which appends the explicitly annotated exact span or spans and any source-verified correction notes; they also receive `noncritical_control` when a reviewed volume control is supplied. Aggregation-gap records receive `stronger_model`, with the board and instructions unchanged. The paper-facing comparison uses the cached original answer on the same cases. Exact replay remains in raw results for diagnostics.

Validate and count calls without paying for inference:

```bash
PYTHONPATH=. .conda-env/bin/python -m scripts.run_frozen_repair run \
  --manifest iclr2027_paper/experiments/repair/qwen235b_silobench_n5_review.jsonl \
  --decisions path/to/reviewed_exact_span_decisions.jsonl \
  --output iclr2027_paper/experiments/repair/dry_run
```

Only after the decisions are reviewed and the API budget is approved, add `--execute --max-calls N` and choose a fresh output directory. `N` must cover the dry-run plan's call count; this is a call-count guard, not a monetary estimate. The runner never overwrites a prior result directory.
