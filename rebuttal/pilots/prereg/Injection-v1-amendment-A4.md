# Injection-v1, amendment A4: extraction candidate expansion (frozen before any call)

2026-11-15. Changes **only the extraction candidate list**. Everything else in `Injection-v1-amendment-A3.md` stays:
the A3 removal rule (base-faithful units plus every unit with fact-token coverage >= 0.6), the sharding candidates and
their 360 attempts, the pooled interleaved order, the 30-kept target per type, the 360-attempt cap per type, and the
$4.00 total cap, counting all logged spend.

## Why

A3 capped each model's candidate list at 120 (first 120 base-eligible instances with a plan). Extraction excludes the
instances already in that model's sharding list. Uncapped, the extraction candidates with a plan are:

- gemma31b: 79 (all of them; the base-eligible pool is 199, of which 120 are sharding candidates)
- gpt4omini: 105 (all of them; eligible 225, 120 sharding)
- qwen235b: 132 (eligible 252, 120 sharding); A3 used the first 120

## Rule

Extraction candidates per model = all base-eligible instances with an extraction plan (A3 plan and removal test),
excluding that model's sharding candidates, in eligibility order, without the 120 cap. The pooled order is unchanged
(rank 1 of each model, then rank 2, ...). The first 304 entries are the A3 candidates, unchanged; the new entries are
the 12 extra qwen235b instances (ranks 121-132). The list is hashed in the build manifest before any call.

Sharding candidates are unchanged (120 per model, 360 attempts). Extraction stops at 30 kept, at 360 attempts, or when
the candidate list is exhausted. With 316 candidates, the list is exhausted first; the 30-kept target cannot be reached
by this rule.

## Cap

The total spend across A2, A3 and A4 (all logged calls) stays within $4.00. The A4 run includes only the new extraction
attempts (12 at most).
