# B6 amendment 2: the sharding input, and a no-unit control

2026-11-15. Amends `B6-audit-guided-repairs.md` (sha `7609e35c...`). Frozen after the first pass ($0.004832)
and before the calls below.

## What the first pass showed

The rule says the sharding repair re-routes "the source support passage for the flagged fact". The first pass
instead fed the **flagged agent's own passage**. For a sharding case that passage by definition lacks the fact,
so all 20 sharding extractions failed the delivery gate. That is an implementation error against the rule, not
a property of the repair.

## Correction (no rule change)

Sharding arm: the input passage is the instance's source support with the **highest gate recall against the
flagged fact** (ties broken by agent id). That is "the source support passage for the flagged fact"; the
flagged agent remains the delivery owner. Extraction prompt, model, token budget and gate are unchanged.

Pass-1 sharding records move to `results_sharding_pass1.jsonl` and stay on record; the 20 pass-1 calls stay in
`calls.jsonl`. The corrected pass issues one extraction call per sharding case and, if delivered, one answer
call.

## Control arm (new)

For every case where the gate delivered units (extraction cell only, 18 cases as of the first pass), one
aggregation call on the **unchanged** board: same prompt, model, token budget, temperature 0. Repaired minus
control is the effect of the delivered units alone; control minus original is any re-run drift. Reported with
the same paired bootstrap.

## Cost

First pass $0.004832. This amendment: at most 20 extraction + 20 answer + 18 control calls, about $0.01 at
measured prices, under the same $5.00 cap and the same chunk rule.