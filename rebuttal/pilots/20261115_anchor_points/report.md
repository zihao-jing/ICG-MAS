# A2 — point-level labeller against the E1 author anchor

2026-11-15. Rule `Anchor-alignment-v1.md` (sha `1d73f49e…`), point prompt `per_fact_points_prompt_v1.json`
(sha `86d84ff6…`), aligned sample `population_aligned.json` (sha `5f1546ce…`). Haiku 5.5 labeller, Gemini
3.6 Flash reference, board checkpoint, temperature 0. Spend **$0.773298**, cap $1.5.

## Result: fails both bars; nothing registered

| Comparison | n | Agreement [95% CI] | κ [95% CI] | Bar |
|---|---:|---|---|---|
| Labeller vs author | 80 | **.488 [.333, .627]** | **.150 [.057, .271]** | .80 / .60 — FAIL |
| Reference vs author | 80 | .513 [.371, .643] | .166 [.068, .286] | — |

Cells (author present, labeller present): 29 both present; 41 author present / labeller not; 10 both absent;
0 author absent / labeller present. 55 instances, cluster bootstrap 2,000 draws, seed 43.

The labeller is specific (all 10 author-absent facts are called absent) and has 29/70 recall under this rule.
The reference behaves almost identically, so the gap is not a Haiku weakness.

## Sample and calls

- 339 E1 anchor fact rows (annotators A and C, one per trace, the same 339 used for the author–author
  κ .530 [.307, .810] and the 10 absent facts). Every fact has exactly one `source_id`, maps to all atoms of
  that agent's support, 0 dropped.
- 80 facts sampled before any call with seed 47: all 10 author-absent + 70 of the 329 present; 55 instances,
  574 atoms.
- 168 calls (80 × 2, plus 8 capped calls re-run once at 6,000 tokens); all parsed. $0.773298.
- **Silo-Bench anchor not run.** Its facts are free-form strings with no ids and its carrier list is flat per
  trace, so it has no per-fact author label to compare against. Running 20 facts there would test nothing.

## Cause, read from the disagreeing facts

The 41 false negatives are not labelling errors on the board text; the authors' fact unit is coarser than
the atom set the rule rolls up. Examples:

| Fact | Author | What the labeller saw |
|---|---|---|
| `A/Anchor Q03 run 1/f_a2` | present | entry gives agent 2's user vectors for users 6, 3, 2, 14, 10 but not the item vector; atom `f_a2.a1` = partial |
| `A/Anchor Q23 run 1/f_a3` | present | entry gives row index 3 for A_rows but not the `A_row_indices` key; 2 of 4 atoms partial |
| `C/Anchor Q18 run 2/f3` | present | entry states socialist realism and government control but omits two other atoms; 3 of 4 not present |

The author marks "Agent N's input records / data shard" present when a faithful **carrier exists**, even when
that carrier restates only part of the shard (role `joint`). The point rule asks whether **every atom** of the
shard is carried. Those are different quantities: carrier existence versus full atom coverage. The anchor's
presence margin is also nearly constant (329/339 present; author–author presence κ 1.000), so it carries
little discrimination to validate a coverage label.

## What this means

- The point label's validated result (atom κ .847 vs the Gemini reference) stands; A2 does not overturn it.
- The point label must not be described as agreeing with author presence labels. Against the anchor's
  carrier-existence label it is .49, and the reference is .51 on the same facts.
- The anchor can still test the label under a **matched** rule: label atoms against only the author's named
  carrier units, and call the fact present if those units carry all its atoms. That tests whether the
  authors' carriers are faithful, which is the claim the anchor actually encodes. Estimated 80 facts ×
  2 models ≈ $0.8; not run here.

## Ledger

$86.882472 before this run + $0.773298 = **$87.655771**. Calls are in `calls.jsonl`; logs `run.log` and
`run_topup.log`.
## Follow-up (zero-cost)

Re-scored the same atom labels under "any atom carried": labeller .925 [.859, .976], kappa .657 [.335, .876];
reference .963 [.900, 1.000], kappa .836 [.541, 1.000]. The A2 failure is the all-atoms roll-up, not the
label. Detail in `any_atom_rule.md`. No calls, no registration.
