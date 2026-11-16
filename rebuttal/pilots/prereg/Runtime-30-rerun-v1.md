# Run-time 30-failure rerun, v1 (frozen before any call; 2026-11-16)

Cap **$2.00** total. Descriptive rerun of the run-time alarm and catch on the 30 failure-enriched MuSiQue traces, with
matched granularity and the answer-bearing gold. No pass bar. Nothing here re-scores the 81 known-cause traces.

## Population

The 30 traces of `rebuttal/pilots/20261115_q1_second_sample` (its `build_manifest.json`, `random_relay`, qwen235b,
answers wrong). Under the answer-bearing gold (below), 26 are scoreable. The 4 not scoreable (2hop__284789_52835,
2hop__525242_52835, 2hop__81659_52835, 3hop1__131820_59747_48534) are listed and excluded from every rate.

## Gold side (fixed; reused at $0)

- Gold pieces: the answer-bearing sentences of the trace, as defined in `prereg/Q1-gold-answer-bearing-amendment-1.md`.
  Ids `a1..aN` in order of appearance.
- Gold labels: `google/gemini-3.6-flash`, prompt `prereg/per_fact_points_prompt_v1.json` (unchanged), checkpoints
  extraction then board (board only if no piece is absent at extraction). Read from
  `rebuttal/pilots/20261116_gold_answer_bearing/results.jsonl` (labeller `google/gemini-3.6-flash` rows only).
- Gold stage: extraction if any piece is absent at extraction; else transmission if any is absent at board; else
  aggregation.

## Run-time side

- Facts: the stored Qwen3-235B proxy facts in `rebuttal/pilots/20261115_proxy_support_mq/facts.json`, prompt
  `prereg/proxy_facts_prompt_v1.json` (sha 1e654d00…). Not regenerated.
- Trace 3hop1__49236_89752_49923: its stored random_relay facts are valid (status ok, 3 facts). Choice: kept, not
  regenerated, not excluded. Regenerating would replace the sample the population was built on.
- Checkpoint labels per proxy fact: stored Haiku 5.5 labels in `20261115_q1_second_sample/results.jsonl` (kind `proxy`),
  reused at $0. Unmerged run-time stage = the trace rule (extraction, transmission, aggregation) on these labels.

## Matched granularity (the one new call per trace)

- One call per trace: `google/gemini-3.6-flash`, temperature 0, max tokens 3000, prompt
  `prereg/proxy_support_equiv_prompt_v1.json` (sha d32272e1…), unchanged.
- GOLD SUPPORTS in the prompt are the answer-bearing pieces, one line each as `[aK] text`.
- Merge: the rule of `prereg/Proxy-gold-merge-v1.md`, applied by `scripts/proxy_gold_merge.py::merge_stage` unchanged,
  with `gold_support_ids = [a1..aN]`. Merged run-time stage = result of that rule.

## Measures (Wilson 95% on each rate)

1. Agreement: merged run-time stage = gold stage, over the 26 scoreable traces. Also the unmerged figure on the same
   26 (recomputed here from stored labels and the new gold).
2. Alarm: the run-time stage names a loss (extraction or transmission). Alarm-real share = share of alarms whose gold
   stage is also extraction or transmission.
3. Catch: over the traces whose gold stage is extraction, the share where the run-time stage is extraction.
   (The 81-trace report uses extraction or sharding; this rerun has no sharding stage, so catch is extraction only.)

Shown beside the new figures: 6/30 (first-support gold, Haiku, `20261115_q1_second_sample/score.json`) and 18/26
(answer-bearing gold, Gemini, unmerged, `20261116_gold_answer_bearing/score.json`).

## Budget and stopping

- Pilot: the first 5 traces in manifest order (one call each), logged with tokens and cost.
- Price: the remaining 25 projected from the pilot's mean cost, priced at the higher Gemini rate in
  `scripts/proxy_support_run.py` ($0.75 / $3.75 per M tokens).
- Run the remaining 25 only if pilot spend + projection < $2.00. Each call is checked against the cap before it is made.
- Every call is logged in `calls.jsonl` with token counts and cost. No log is deleted.

## Outputs

`rebuttal/pilots/20261116_runtime_30_rerun/`: `build_manifest.json` (this file's sha256, the gold, facts and label
source hashes, the 26 and 4 lists), `calls.jsonl`, `equiv.jsonl`, `score.json`, `report.md`.
