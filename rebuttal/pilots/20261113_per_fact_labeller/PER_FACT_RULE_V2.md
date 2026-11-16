# Frozen rule v2: per-fact labeller, target changed to the authors' carrier units

Written 2026-11-13 before the rescoring rerun. Zero model calls: it re-scores
the frozen v3 labeller output already logged in `results.json`. The semantic
fidelity target and its FAIL stay on record in `report.md`; this file changes
**what the target is**, not the prompt or the calls.

## Why (option b)

The semantic target asks whether the board states each listed fact. The
authors' carrier records frequently mark a fact faithful with a unit that does
not state it (e.g. `2hop__28287_89399 / C`: the annelid-reproduction fact is
marked faithful with "Annelid fertilized eggs develop into trochophore
larvae..."). That target is therefore not reproducible by a faithful labeller.

What the authors actually labelled is **which board units carry each fact**:
`carriers_json`, checkpoint `board`, `unit_ids` (joint carriers list several).
The target is changed to that label. The labeller is not re-prompted; its
already-logged `unit_ids` are scored against the author's.

## Target definition (fixed before the rescoring)

For each author annotation and fact:

- Author carrier set = the union of `unit_ids` in that annotation's
  `carriers_json` rows with `checkpoint == "board"` for the fact.
- Labeller carrier set = the `unit_ids` returned by the frozen v3 call for that
  fact, unless status is `absent` (then empty).
- The fact is **matched** iff the two sets intersect.

Trace complete under the authors' combining rule = every listed fact is
matched. This is compared with the same annotation's `author_complete`.

## Population and pass rule (unchanged)

The validation split of `split.json`: 8 instances x 3 models x 2 annotations =
48 board comparisons. Pass: agreement >= 0.80 and Cohen's kappa >= 0.60.
Exact Clopper-Pearson for agreement; instance-cluster bootstrap for kappa
(seed 43, 10,000 draws).

## What a pass means

A pass validates **carrier-unit identification against the author labels**.
It does not validate semantic fidelity, and it does not license redrawing the
main-table coverage, critical-recall, omission, fidelity or AF columns: those
need a semantic target the audit can apply to its own fact list. The old
semantic FAIL remains the reason they stay lexical. No paper edit, no commit.