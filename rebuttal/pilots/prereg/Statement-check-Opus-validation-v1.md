# Validation of the statement shard check against Opus 5.5 (frozen before any call)

2026-11-16. Stage: sharding presence check (the Haiku 5.5 statement check of `Sharding-presence-semantic-v1`). Validation only; no audit cell is rescored under this file. Validation cap **$5.00**.

## Why

The statement check (`prereg/Sharding-presence-semantic-v1.md`) was validated on other checkpoints (κ .847 and .780), not at the shard checkpoint, and it was run as a sensitivity rule. Its labels decide whether a missing fact is `absent` from the source shards, which routes a trace to sharding. This file checks those labels at the shard checkpoint against an independent reference.

## Population

The 71 (case, fact) statement-check jobs of `rebuttal/pilots/20261115_sharding_semantic` (`results.jsonl`, `calls_to_make.json`), read through `scripts/sharding_semantic_run.jobs()`. Haiku labels: present 38, absent 32, partial 1.

## Sample (fixed)

For each job, `sha256("47|f39|" + key + "|" + fact_id)`. Sorted ascending by that hash, then the first jobs are taken per Haiku label up to the quota:

| Haiku label | Quota | Taken |
|---|---:|---:|
| present | 14 | 14 |
| absent | 15 | 15 |
| partial | 1 | 1 (the only partial job) |

Total 30. The sample is written to `rebuttal/pilots/20261116_statement_opus_validation/sample.json` and its sha256 is recorded in `build_manifest.json` before any call.

## Reference and prompt

- Reference: `claude-opus-5-5` through the local Claude Code CLI (headless print mode), run from an empty temporary directory, tools off, the fixed system prompt of `prereg/per_fact_points_prompt_v1.json` (same prompt and same user text as the Haiku run).
- Output parsed with `scripts/per_fact_points_run.parse`. Opus status per atom rolls up with `scripts/sharding_semantic_run.rollup` (present = every atom present; absent = every atom absent; otherwise partial).
- Each call is logged in `calls.jsonl`. No call is repeated after a result is recorded.

## Bars (fixed here)

All five must hold for the Haiku statement check to be validated at the shard checkpoint:

1. Valid Opus outputs: at least 28 of 30.
2. Three-class rollup agreement (Haiku vs Opus): at least 0.85.
3. Unweighted Cohen's κ, three classes: at least 0.70.
4. Absent-vs-not agreement (absent = the label that routes to sharding): at least 0.90.
5. Precision of Haiku's `absent`: among Haiku `absent` labels, the share Opus also labels `absent`: at least 0.85.

Intervals: Wilson 95% on each rate. The partial class has one job in the population, so κ and per-class figures are reported as descriptive only.

## Decision

If all five bars hold, the statement check is validated at the shard checkpoint and may be written as the audit's shard rule in a new frozen rule before it is scored on the 82 runs. If any bar fails, the statement check is not used as the shard rule; the failure and the misses it leaves are reported.

## Limits fixed here

- Sample of 30 from 71 jobs; the bars are indicative at this size, not a population estimate.
- One partial job: no per-class claim about partial labels.
- Opus output that does not parse counts as invalid, not as disagreement.
- Cap $5.00; the run stops before a call that would exceed it.
