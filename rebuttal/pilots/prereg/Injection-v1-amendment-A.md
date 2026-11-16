# Injection experiment v1, amendment A — frozen before any call

2026-11-15. Replaces the sharding and extraction injection sections of `Injection-v1.md` (that file stays on
record). Base eligibility, backbones, methods, the 40-attempt cap, retention quota, and the $4.00 cap are
unchanged. This file is hashed into the build manifest of `20261115_injection_amendA/` before any call.

## Base eligibility (unchanged from Injection-v1)

Stored MuSiQue `score_ranked_relay` traces of the paper models whose matcher record has status `ok`,
`answer_correct` true, and every carrier at the extraction and board checkpoints `faithful`. Order per model:
`sha256("injection-v1|20261115|<model>|<instance_id>")`, ascending.

## Candidate lists (fixed before any call)

- Sharding candidates: the first 40 base-eligible instances, in model order, that have a sharding plan.
- Extraction candidates: the first 40 base-eligible instances, in model order, that have an extraction plan and
  are not sharding candidates.

Each candidate is used at most once per type. Attempts advance through the list in order.

## Content tokens and sentence coverage (used by the sharding plan)

- `T(x)` = set of normalized alphanumeric tokens of `x` with length greater than 2.
- `F` = `T(fact text)` for the critical fact.
- Coverage of a sentence `s` = `|F ∩ T(s)| / |F|`.
- Sentences are split on `(?<=[.!?])\s+`. A target sentence must occur verbatim in the shard text.

## Sharding injection (true stage = sharding)

1. Anchor fact: the first critical fact in `fact_id` order that has at least one faithful extraction carrier.
   Its owner is the agent of that carrier's first unit. If the owner's shard holds no target sentence, the next
   fact in order is tried. The plan is the first fact that passes.
2. Target sentences: every sentence in every agent's shard (`source_contexts`) with coverage at least 0.5.
3. Delete every target sentence from its shard, in all agents. The plan requires at least one target in the owner's
   shard. Everything else in each shard is unchanged.
4. Every agent whose shard changed reruns extraction with the unchanged extraction prompt and model. Its new
   units are scored with the unchanged scoring prompt and model. All agents' top-3 selection is then recomputed
   with the unchanged rule. Agents whose shard did not change keep their stored transmission. The unchanged
   aggregation prompt and model are run. The final answer is the new aggregation output.

## Extraction injection (true stage = extraction)

1. Anchor fact: the first critical fact in `fact_id` order that has at least one faithful extraction carrier, at
   least one faithful board carrier, and at least one of its faithful extraction units in its agent's base
   transmission list.
2. Removed: every extraction-pool unit, in any agent, that the base record marks as a faithful carrier of the fact.
   The shards are kept intact.
3. The affected agents' selections are recomputed from their remaining units and stored scores, with the unchanged
   top-3 rule. Other agents keep their stored transmission. No extraction or scoring call is made. The unchanged
   aggregation prompt and model are run.

## Post-injection check (validated presence labeller)

- The labeller is the Qwen-235B carrier step (`CARRIER_PROMPT`, `carrier_schema`), the same backbone and prompt that
  produced the stored base records. Its validation: extraction presence κ .780, board κ .857.
- It is run on the injected trace. The check passes when no extraction-pool unit is labelled `faithful` for the
  injected fact.
- For sharding, this tests whether the fact reached the pool from any remaining shard text. Shard text is not
  labelled separately; the mechanical deletion is the shard-level step, and the pool check is its test.

## Retention

A case is kept only if (a) the final answer's F1 against the gold answer is below 1.0, and (b) the post-injection
check passes. The check runs only on cases whose answer is wrong. Cases are logged with their answer F1 and check
result, whether kept or not.

Quota: 10 kept per paper model per type (30 per type), at most 40 attempts per model and type.

Pilot: 1 kept per paper model per type (3 per type), run first. Its yield and the projection for 30 per type are
reported before any full run.

## Methods (unchanged from Injection-v1)

Audit without and with the sharding-rule fix, each on Qwen-235B and Gemini 3.6 Flash; Who&When-style judge on each
backbone; [R1] on each backbone (released prompt, `R1-coordinate-stage-map.md`, sha `2015e084…`).

## Spend

Cap $4.00 for the experiment in total. The spend already recorded in `20261115_injection/calls.jsonl`
($0.208927) counts toward the cap. Calls are logged with model, tokens and cost.

## Not part of this rule

The base-trace calls and the stored corrupted-relay and cohort results are not changed. The earlier pilot in
`20261115_injection/` stays on record as it is.
