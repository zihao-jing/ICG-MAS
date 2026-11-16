# 7b — matched anchor check (author-named carrier units only)

2026-11-15. Rule `Anchor-alignment-matched-v1.md` (sha `cbbdec70…`), source population `population_aligned.json`
(sha `5f1546ce…`), matched population `population_matched.json` (sha `f10bd1c7…`). Haiku 5.5 labeller,
Gemini 3.6 Flash reference, same 80 facts (seed 47), board checkpoint. Spend **$0.566843**, cap $1.0.

## Result: fails both bars; nothing registered

| Comparison | n | Agreement [95% CI] | κ [95% CI] |
|---|---:|---|---|
| Labeller vs author | 80 | **.488 [.329, .625]** | **.150 [.058, .277]** |
| Reference vs author | 80 | .513 [.362, .643] | .166 [.069, .288] |

Cells (author present, labeller present): 29 both present; 41 author present / labeller not; 10 both absent;
0 author absent / labeller present. 55 instances, cluster bootstrap, 2,000 draws, seed 43.

The evidence set was rebuilt for all 80 facts — 57 facts have 3 carrier units, 10 have none, the rest 1–2,
against 2–30 board units in A2 — and **not one fact-level verdict changed**. Every key's labels differ in
the text, but the 41 false negatives persist, and the 10 empty-evidence facts are all absent on both sides.

## Cause

Restricting the evidence to the authors' carriers did not change which atoms are carried: the atoms missing
from the whole board were already missing from the authors' own carrier units. The mismatch is therefore in
the **fact-to-atom mapping**, not in the evidence pool. The authors' fact is "Agent N's input records /
data shard" — one coarse unit. The rule maps it to every atom of that shard and requires all of them; the
author's "present" means the shard is represented, not that every element of it is carried. A shard-level
fact and a per-element atom set are different units.

## What this rules out and what is left

- Ruled out: the A2 failure is not caused by showing the labeller too much evidence. Narrowing to the
  authors' carriers does not move a single verdict.
- Left: a matched test needs each author fact aligned to the atoms **it names**, not to every atom of its
  source. That needs a semantic alignment call (one per fact, ~80 calls) and then the same point labelling.
  Estimated under $0.6; not run here.

## Ledger

$87.655771 before this run + $0.566843 = **$88.222614**. Calls in `calls.jsonl`; logs `run.log`,
`run_topup.log`.