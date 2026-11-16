# Injection experiment v1 — rule, frozen before any case is generated

2026-11-15. Approved as step 2 of the rebuttal plan. This file is hashed into
`build_manifest.json` before any call and before any case is generated.

## Question

Do the three attribution methods (evidence-flow audit, Who&When-style judge, [R1]) name the right stage on
failures whose stage is known by construction, when the failure is a sharding loss or an extraction loss rather
than a corrupted relay?

## Base runs

Base runs are the stored Stage-2 MuSiQue `score_ranked_relay` traces of the paper models
(`gemma31b` = google/gemma-4-31b-it, `gpt4omini` = openai/gpt-4o-mini, `qwen235b` =
qwen/qwen3-235b-a22b-2507). A base run is eligible only if all of the following hold, read from its stored
matcher record and trace package:

1. the matcher record status is `ok` and `answer_correct` is true;
2. every critical fact has at least one faithful carrier at the extraction checkpoint and at least one
   faithful carrier at the board checkpoint;
3. every carrier at both checkpoints has fidelity `faithful` (no `partial`, `uncertain`, `absent` or
   `distorted`).

Condition 2 and 3 are the validated presence labels: the carrier-presence step is the one validated at
agreement .900 and κ .722 on 120 units before the 2x2. The final-answer checkpoint is the base answer, and its
correctness is condition 1.

For each model, eligible instances are ordered by
`sha256("injection-v1|20261115|<model>|<instance_id>")`, ascending. This order is frozen.

## Sharding injection (true stage = sharding)

Take the first case in the model's order for which a plan exists. A plan exists when, iterating the base
record's facts in `fact_id` order, some fact has a faithful extraction carrier, and:

- the owning agent is the agent of that fact's first faithful extraction-carrier unit;
- the owning agent's gold support paragraph is split into sentences on `(?<=[.!?])\s+`;
- of those sentences, the one with the highest content-token Jaccard overlap with the carrier unit's text is
  chosen; ties go to the earliest sentence; overlap must be greater than zero and the sentence must occur
  verbatim in the owning agent's stored context;
- that sentence is deleted from the owning agent's private shard (in `source_contexts` and from the shard
  passed to the owning agent's extraction prompt). Everything else in the shard is unchanged.

Then the owning agent's extraction is rerun with the unchanged extraction prompt and model, its new units are
scored with the unchanged scoring prompt and model, all agents' top-3 selection is recomputed with the
unchanged selection rule (other agents' stored scores and units unchanged), and the unchanged aggregation
prompt and model are run. No other call changes. The final answer is the new aggregation output.

## Extraction injection (true stage = extraction)

Take the first case in the model's order (not already used for sharding on the same base instance) for which a
plan exists. A plan exists when, iterating facts in `fact_id` order, some fact has at least one faithful
extraction carrier and at least one faithful board carrier, and every extraction-carrier unit for that fact is
present in that agent's base transmission list.

The shard is kept intact. Every extraction-carrier unit of that fact is removed from the owning agent's
stored extraction list before transmission. The owning agent's selection is recomputed from the remaining
units and their stored scores under the unchanged top-3 rule; other agents' selections are unchanged. The
unchanged aggregation prompt and model are run. No extraction or scoring call is needed.

## Retention

A generated case is kept only if the new final answer is wrong (answer F1 < 1.0 against the gold answer).
If the answer is correct, the next eligible case in the frozen order is used. Quota: 30 kept sharding cases
and 30 kept extraction cases, stratified ten per paper model, with at most 40 attempts per model and type.
The pilot uses the first case in each model's order for each type; if that answer is correct, it advances in
the same order. Pilot cases are part of the full quota and are not rerun.

The generated trace is written with the modified source context, the new extraction/transmission/board
checkpoints, the new answer, and the known stage (`sharding` or `extraction`).

## Methods (each on Qwen-235B and Gemini 3.6 Flash)

- **Audit, without the sharding-rule fix.** The base trace's Qwen-generated critical facts (generated from the
  gold supports, so unaffected by the injection) are carried through the unchanged carrier-labelling prompt
  with the named backbone on the injected trace. The unchanged `diagnose_with_sharding` lexical rule maps the
  label to a stage.
- **Audit, with the sharding-rule fix.** Same facts and carrier labels; when the diagnosis is
  `extraction_omission`, the shard-presence decision for each missing fact uses the statement-based atom rule
  (`per_fact_points_prompt_v1.json`, Haiku 5.5), and the frozen roll-up and stage mapping of
  `Sharding-presence-semantic-v1.md` are applied.
- **Judge.** The frozen Who&When-style attribution prompt with the named backbone, on the injected trace.
- **[R1].** The released prompt and parser, stage read from the released step coordinate under
  `R1-coordinate-stage-map.md` (sha `2015e084…`), with the named backbone.

Every call is logged with model, tokens and `cost_usd`. Cap: **$4.00 total** for the injection experiment,
including the pilot. The pilot (3 kept cases per type, one per model) is run first; the measured per-case cost
and the projection for the full run are reported before the full run starts.

## Not part of this rule

The existing 30 corrupted-relay cases are reused as the third row of the report; their method cells are the
stored results of the 89-case runs and no new call is made for them. The 59-case cohort is reported as the
secondary row from the same stored results. No paper edit and no commit.