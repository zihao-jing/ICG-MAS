# Matched anchor check of the point-level presence label: rule v1

2026-11-15, frozen and hashed before any call. Step 7b, following A2 (`Anchor-alignment-v1.md`).

## What changes from A2

A2 gave the labeller the whole board and required every atom to be present; the authors instead mark a fact
present when a faithful **carrier** exists. This rule uses only the units the authors named as carriers, so
both sides answer the same question.

## Evidence

- For each fact, the evidence is exactly the author's carrier units at the **board** checkpoint: the board
  entries whose `unit_id` appears in that fact's carrier row (`carriers_json`, `unit_ids`).
- A fact whose carrier row has `fidelity: absent` and no units gets an **empty** evidence set.
- No other board unit is shown to the labeller.

## Labels

- **Author present**: the fact has a carrier row at the board whose `fidelity` is not `absent` (the same
  definition as A2).
- **Labeller present**: every atom of the fact is `present` in the author-named units, by the frozen point
  prompt and roll-up. If the evidence set is empty, every atom is `absent`.
- Reference: Gemini 3.6 Flash, identical prompt; reported beside the labeller.

## Sample

Identical to A2: the same 80 facts drawn with seed 47 (all 10 author-absent + 70 of 329 present), same
instances, same order, same population file (`population_aligned.json`, sha `5f1546ce…`). The matched build
only replaces each row's `entries` with the author's carrier units and records its own sha.

## Metrics and bars

- Binary agreement and Cohen's κ against the author labels, 95% instance-cluster bootstrap (2,000 draws,
  seed 43), same cell layout as A2 (author present × labeller present).
- Bars: agreement ≥ .80 and κ ≥ .60; pass requires both. Register nothing unless both pass.
- κ is reported with its CI and the same prevalence caveat (the author margin is 70/80 by construction).

## Models and cap

Haiku 5.5 labeller, Gemini 3.6 Flash reference, temperature 0, one call per (fact, model). Cap **$1.0**;
every call logged; stop if the projection would exceed the cap. The point rule and prompt are unchanged.