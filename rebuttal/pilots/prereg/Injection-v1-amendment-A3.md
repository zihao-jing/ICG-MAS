# Injection experiment v1, amendment A3 — frozen before any call

2026-11-15. Replaces the extraction-injection removal rule and the quota/cap rule of `Injection-v1-amendment-A2.md`.
A2 stays on record with its pilot in `20261115_injection_amendA2/`. Everything not named here is unchanged from A2
(base eligibility, backbones, segmentation, sharding injection, methods, residue labeller and residue rule, $4.00
cap). This file is hashed into the build manifest of `20261115_injection_amendA3/` before any call.

## Why A3

`scripts/injection_removal_check.py` (zero cost, `rebuttal/pilots/20261115_injection_removal_test/removal_check.json`)
found that A2's extraction removal deletes only the units the base carrier labeller marked `faithful`. Across the
304 A2 extraction candidates, 124 still contained a pool unit with at least 0.6 of the anchor fact's content tokens
after that removal (49 with two or more). Example: `2hop__189094_612080` (gemma31b): one base-faithful unit removed,
three further units, each with coverage 0.6, left in the pool. A2 is therefore not a removal of every copy.

The A2 pilot also gave 1 kept case in 3 of the 6 pilot slots for extraction (gemma31b, gpt4omini; qwen235b 0 of 120),
and A2's per-model quota of 120 attempts stopped qwen235b extraction with no kept case. A3 changes the quota rule so
that the target is pooled across models.

## 1. Extraction removal (replaces A2 "Extraction injection", step 2)

Anchor fact, residue labeller and all other steps are as in A2 (`plan_extraction`). The removed set is:

- every extraction-pool unit that the base record marks as a faithful carrier of the anchor fact (A2 rule), **union**
- every extraction-pool unit `u` with coverage `|F ∩ T(u)| / |F|` at least **0.6** (the same `COVER` and `T` as the
  sharding rule), where `F = T(anchor fact text)`.

Shards are kept intact. Affected agents' selections are recomputed from the remaining units and stored scores, as in A2.

The removal test in `scripts/injection_removal_check.py` must show 0 units with coverage at least 0.6 left in the pool
for every A3 extraction candidate before any call. Its output is on record in
`20261115_injection_removal_test/removal_check.json`.

## 2. Sharding injection

Unchanged from A2. Sharding calls, keys and cached outputs are reused where the inputs are identical.

## 3. Candidate lists

Unchanged from A2: first 120 base-eligible instances per model and type with a plan (sharding first; extraction
excludes sharding candidates). The extraction plan now includes the lexical units of step 1.

## 4. Quota, order and cap (replaces A2 "Quota" and "Pilot")

- **No per-model quota.** Target: **30 kept cases per type**, pooled across the three paper models.
- **Order:** for each type, candidates are interleaved by model: rank 1 of each model in model order, then rank 2,
  and so on. Each candidate is attempted once; a candidate already in the results is skipped.
- **Stop per type:** at 30 kept, or at **360 attempts** of that type (all models together, 120 per model in
  principle; the pooled order can reach at most 360 entries).
- **Cap:** $4.00 for the experiment in total. Spend in `20261115_injection/`, `20261115_injection_amendA/` and
  `20261115_injection_amendA2/` calls logs counts toward the cap and their successful calls are read as caches.
- A call that would exceed the cap stops the run; the run then reports what it has. It is not continued past the cap.

## 5. Kept case, residue and methods

Unchanged from A2: a case is kept when the answer is not F1 1.0, the residue check passes (no non-absent extraction
copy by the Qwen-235B carrier step), and the labeller did not fail. Kept cases run all methods (audit under the token-
overlap and statement shard checks, Who&When-style judge, [R1]) on Qwen-235B and Gemini 3.6 Flash, as in A2.

## 6. Report (for the user's review, before any method is scored beyond the kept set)

Per type and per model: attempts, F1-1.0 (answer unchanged), residue failures (by fidelity class), labeller failures,
kept. Spend per type and total, against the cap. No result is reported as a rate without its Wilson 95% interval.
