# Anchor check of the point-level presence label: alignment rule v1

2026-11-15, frozen and hashed before any call. Applies the frozen point-level labeller
(`Per-fact-presence-points-v1.md`, prompt `per_fact_points_prompt_v1.json`) to the author anchor facts.

## Source

- **E1 anchor**, `rebuttal/annotation/returns/E1anchor_{A,C}_labelling-v1.0.json`: 90 traces, one primary
  annotator per trace (A for the A/B traces, C for the C/D traces), 339 critical-fact rows. This is the same
  339-fact set used for the author–author κ .530 [.307, .810] and the 10 absent facts (329 present).
- **Silo-Bench anchor**, `rebuttal/annotation/packets_20261110/returns/SB_anchor/`: 30 traces per annotator.
  Its critical facts are free-form strings with no ids and its carrier list is flat per trace, so it has no
  per-fact author label. **It cannot be scored at fact level and is not run** (no calls spent). The 20-trace
  budget line is therefore not used; the reason is recorded rather than a comparison that tests nothing.

## Alignment

1. An author fact is kept only if it has **exactly one** `source_id` (`agent-N`) and no other.
2. Its atoms are **all atoms of the source support whose `support_id` is that `agent-N`**, split by the same
   atomizer as the point rule (list elements, dict keys, sentences; `scripts/per_fact_points_build.py`).
3. A fact is dropped if the source id has no support or the support yields zero atoms. Dropped facts are
   counted and reported.

## Labels compared

- **Author present**: the fact has at least one carrier row at the **board** checkpoint whose `fidelity` is
  not `absent`. Otherwise absent. (All 339 facts have a board carrier; 10 have only `fidelity: absent`.)
- **Labeller present**: every mapped atom is `present` at the board, by the point rule's roll-up. Any
  `partial` or `absent` atom makes the fact not present.
- Checkpoint: board. The pool is not compared here.

## Sample

- 80 facts, seed 47: **all 10 author-absent facts plus 70 of the 329 author-present facts**, drawn without
  replacement by a seeded hash. Order by hash. Written to `population_aligned.json` before any call.

## Metrics and bars

- Binary agreement and Cohen's κ over the 80 facts, each with a 95% instance-cluster bootstrap CI (2,000
  draws, seed 43, clusters = anchor instances that contribute facts).
- Bars: agreement ≥ .80 and κ ≥ .60. Pass requires both point estimates. κ is reported with its CI and with
  the prevalence caveat: the author margin is 70/80 by construction, so a high agreement is expected and κ
  carries the discrimination signal.
- If κ is undefined (constant margin), report the raw cells and agreement only.

## Models and cap

- Labeller Claude Haiku 5.5, reference Gemini 3.6 Flash, identical point prompt, temperature 0, one call per
  (trace, fact). Cap **$1.5**; every call logged; stop if the projection would exceed the cap.

## Registration

Register nothing unless both bars pass. If they fail, report the disagreeing facts and the cause.