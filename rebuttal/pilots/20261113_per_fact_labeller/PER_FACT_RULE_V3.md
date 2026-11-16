# Frozen rule v3: fresh held-out check of the carrier-identification target

Written 2026-11-13 before any reserve call. The carrier target was chosen after
the semantic target failed on the 8-instance validation split, so that 41/48
PASS is **post hoc** and is labelled "exploratory carrier-identification pass,
n=48". This rule runs the same frozen prompt and carrier rule on traces that
were not used for the target change: the **reserve** split of `split.json`
(5 instances, never called and never read during tuning or the target change).

## Population

Reserve instances: 5, their matcher-ok traces (up to 15) and both author
annotations. Calls: one per trace x annotator x checkpoint with the frozen
`per_fact_prompt_v3.json` (system sha256 `3f7f19bb...`), temperature 0, same
renderer and parser as before. Cap $5; every call logged in `calls.jsonl`.

## Target and pass rule

Exactly `PER_FACT_RULE_V2.md`: author board carrier units per fact; a fact
matches when the labeller's returned units intersect the author's; complete =
every fact matches; compare with `author_complete`. Pass: agreement >= 0.80
and Cohen's kappa >= 0.60 on the reserve board comparisons. Exact
Clopper-Pearson for agreement; instance-cluster bootstrap for kappa (seed 43,
10,000 draws). Per-fact carrier match is reported.

## What a pass means

Carrier identification only. It does not validate semantic fidelity or
semantic coverage, and the main-table coverage, fidelity and related columns
stay on the lexical or matcher figures. The semantic FAIL stays in `report.md`
beside this result, not replaced by it.

If the reserve fails, the labeller stays unvalidated and no further author
labels remain in the anchor; a new validation would need new annotation.