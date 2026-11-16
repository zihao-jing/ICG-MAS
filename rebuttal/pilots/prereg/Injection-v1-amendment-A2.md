# Injection experiment v1, amendment A2 — frozen before any call

2026-11-15. Replaces the injection sections of `Injection-v1-amendment-A.md` (that file stays on record, with
its pilot in `20261115_injection_amendA/`). Base eligibility, backbones, methods, retention quota and the $4.00
cap are unchanged. This file is hashed into the build manifest of `20261115_injection_amendA2/` before any call.

Two defects in the amendment-A pilot are fixed here: (1) sharding deleted whole document blocks, because
sentences were split on punctuation only; (2) the residue check counted only `faithful` copies, so `partial`
and `distorted` copies passed.

## Base eligibility, candidate lists, models

Unchanged from `Injection-v1.md`. Stored MuSiQue `score_ranked_relay` traces of the paper models with matcher status
`ok`, `answer_correct` true, and every carrier at extraction and board `faithful`. Order per model:
`sha256("injection-v1|20261115|<model>|<instance_id>")`, ascending.

- Sharding candidates: the first **120** base-eligible instances, in model order, that have a sharding plan.
- Extraction candidates: the first **120** base-eligible instances, in model order, that have an extraction plan
  and are not sharding candidates.
- Attempts advance through each list in order; at most **120 attempts per model and type**.

## Segmentation (used by the sharding plan)

1. Split the shard text on line breaks.
2. Drop scaffolding lines: any line beginning `Question:`, `You hold the following evidence`, or `[Document:`.
3. Split each remaining line on `(?<=[.!?])\s+`. Each piece is a sentence. A target must occur verbatim in its shard.

## Content tokens and coverage

- `T(x)` = normalized alphanumeric tokens of `x` with length greater than 2.
- `F` = `T(fact text)`. Coverage of a sentence `s` = `|F ∩ T(s)| / |F|`.
- A sentence **states the fact** when its coverage is at least **0.6**.

## Sharding injection (true stage = sharding)

1. Anchor fact: the first critical fact in `fact_id` order with at least one faithful extraction carrier. Its owner is
   the agent of that carrier's first unit. The plan requires at least one sentence that states the fact in the
   owner's shard; otherwise the next fact is tried.
2. Delete every sentence that states the fact, in every agent's shard. Nothing else in any shard changes.
3. Every agent whose shard changed reruns extraction (unchanged prompt and model), scores its new units (unchanged
   scoring prompt and model), and all agents' top-3 selection is recomputed (unchanged rule). Unchanged agents keep
   their stored transmission. The unchanged aggregation prompt and model are run.

## Extraction injection (true stage = extraction)

1. Anchor fact: the first critical fact in `fact_id` order with at least one faithful extraction carrier, at least one
   faithful board carrier, and at least one of its faithful extraction units in its agent's base transmission.
2. Remove every extraction-pool unit, in any agent, that the base record marks as a faithful carrier of the fact.
   Shards are kept intact.
3. Affected agents' selections are recomputed from remaining units and stored scores (unchanged top-3 rule). No
   extraction or scoring call. The unchanged aggregation prompt and model are run.

## Post-injection check (validated presence labeller)

- Qwen-235B carrier step (`CARRIER_PROMPT`, `carrier_schema`), the backbone and prompt of the stored base records.
  Validation: extraction presence κ .780, board κ .857.
- It runs on the injected trace. **Residue** = any extraction-pool carrier entry for the injected fact whose
  fidelity is not `absent` and that has at least one unit id. Faithful, partial, distorted and uncertain all count.
- **Pass** = no residue. A labeller failure is not a pass.

## Retention

A case is kept only if (a) the final answer's F1 against gold is below 1.0, and (b) the check passes. The check runs
only on cases whose answer is wrong. Every attempt is logged with its F1, its check result, and the sentences or
units deleted.

Quota: 10 kept per paper model per type (30 per type), within the 120-attempt cap.

**Pilot: 1 kept per paper model per type (3 per type), run first.** The full run starts only after the user's review.

## Methods (unchanged)

Audit without and with the sharding-rule fix, each on Qwen-235B and Gemini 3.6 Flash; Who&When-style judge on each
backbone; [R1] on each backbone (`R1-coordinate-stage-map.md`, sha `2015e084…`).

## Spend

Cap $4.00 for the experiment in total. Spend already recorded in `20261115_injection/calls.jsonl` ($0.208927) and
`20261115_injection_amendA/calls.jsonl` ($0.164337) counts toward the cap. Each call is logged with model, tokens and
cost.

## Not part of this rule

The v0 and amendment-A pilot outputs stay on record as they are.
