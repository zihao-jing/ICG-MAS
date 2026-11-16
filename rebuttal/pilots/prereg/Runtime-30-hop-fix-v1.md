# Run-time 30 with hop-by-hop fact generation, v1 (frozen before any call; 2026-11-16)

Step 48. Fix attempt for the run-time version's agreement on the 26 scoreable traces of `Runtime-30-rerun-v1.md`
(18/26 before the fix). Cap **$2.00** total for this attempt. Descriptive; no pass bar.

## Question

Does generating the run-time facts hop by hop (the first hop's bridge entity first, then the facts needed about that
entity) change the run-time agreement with the gold stage, on the same 26 traces, with the gold, the matched
granularity and the Gemini labeller unchanged?

## Population

The 26 scoreable traces listed in `rebuttal/pilots/20261116_runtime_30_rerun/build_manifest.json` (`scoreable_list`).
The 4 not scoreable traces stay excluded, as before. Gold pieces and gold stage are read from
`20261116_runtime_30_rerun/inputs.json` (unchanged; gold labels from `20261116_gold_answer_bearing`, Gemini).

## The one change: fact generation

- Generator: `qwen/qwen3-235b-a22b-2507`, temperature 0, max tokens 4096 (as in v1).
- Prompt: `prereg/proxy_facts_hop_prompt_v2.json` (sha256 384d64fb3a627e90b79c17f9df1cc049d48a499e1dd8027bff2ab60696843575).
  It is `prereg/proxy_facts_prompt_v1.json` (sha 1e654d00…) with one added paragraph in the system text, the
  "Bridge-first rule". The user text, output schema and validation are unchanged.
- Validation: `scripts/proxy_support_run.py::validate_facts` unchanged; up to 3 attempts per trace, as in v1.

## Unchanged from the 26 run

- Checkpoint labels: `anthropic/claude-haiku-5.5`, prompt `prereg/per_fact_points_prompt_v1.json`
  (sha 86d84ff6…), rendered as in `scripts/q1_second_sample.py` (atoms split on '. ', extraction and board texts
  from `20261115_proxy_support_mq/population.json`). One label per new fact at each checkpoint.
- Trace stage from the labels: `scripts/proxy_gold_merge.py::trace_stage`, unchanged.
- Matched granularity: `google/gemini-3.6-flash`, prompt `prereg/proxy_support_equiv_prompt_v1.json` (sha d32272e1…),
  one call per trace, merge by `merge_stage` (`prereg/Proxy-gold-merge-v1.md`), unchanged.
- Measures and Wilson 95%: as in `Runtime-30-rerun-v1.md` (agreement, alarms and alarm-real, catch on extraction gold).

## Comparison shown beside the result

- Before the fix: merged agreement 18/26 (69%, Wilson 50–84) and alarms 4 (1 real), catch 1/6, from
  `rebuttal/pilots/20261116_runtime_30_rerun/score.json`.

## Budget and stopping

- Pilot: the first 5 traces in manifest order (facts, labels and equivalence for each), every call logged.
- Price: the remaining 21 traces projected from the pilot's mean cost per trace. The projection uses the same per-call
  price table as the earlier runs.
- Run the remaining traces only if pilot spend + projection < $2.00. Each call is checked against the cap before it is
  made.
- Logs: `rebuttal/pilots/20261116_runtime_30_hop/calls.jsonl` (tokens and cost per call). No log is deleted.

## Outputs

`rebuttal/pilots/20261116_runtime_30_hop/`: `build_manifest.json` (this file's sha256, the prompt sha256, the trace
list), `facts.json`, `labels.json`, `inputs.json`, `equiv.jsonl`, `calls.jsonl`, `score.json`, `report.md`.
