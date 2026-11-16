# E2-C main run (frozen before the first baseline call)

Date: 2026-11-14. Stage: baseline attribution on the k = 1 Part B boards.
Descriptive casebook only; no scoring and no pooling of backbones.

## Population

The 156 frozen Part B k = 1 traces (`20261114_part_b_k1/answers.jsonl`) with
their sealed E1 judge labels. Class rule, applied to the judge's carriers:

- extraction: `binary_call = lost` and a fact has no pool carrier;
- selection: `binary_call = lost`, a fact has a pool carrier and no board carrier;
- aggregation: `binary_call = reached_but_unused`.

Cells and counts, fixed before any call: Silo-Bench extraction (up to 4),
Silo-Bench selection (up to 4), MuSiQue aggregation (2), Silo-Bench
aggregation (2). Within a cell, order by
`SHA-256(json([42, model, instance_id]))` and take the first k; if fewer exist,
take all and report the shortfall. No picking after output.

## Calls

Three released methods on each trace and each of two backbones (Qwen-235B and
Gemini 3.6 Flash): Who&When all-at-once (MIT), Who&When-Pro `all_at_once`
with the released 17-mode taxonomy, and MAST. Six calls per trace. Temperature
0, max output 4,096. Cap **72 calls / $2.00**. The Gemini-backbone rows are
stored separately and marked "judged by the same model"; they are never pooled
with the Qwen rows.

## Scoring

No score is computed in this run. Any later judge scoring of these outputs
uses only a Gemini judge whose agreement with the frozen Opus 5.5 reference
has passed the E2-C validation (agreement >= 0.80, kappa >= 0.60, 95% CIs).