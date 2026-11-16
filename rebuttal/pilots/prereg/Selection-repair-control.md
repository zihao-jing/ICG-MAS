# Selection-repair control on the MuSiQue E3 selection routes (frozen before any call)

Date: 2026-11-14. Stage: relay aggregation after a targeted request.

## Population

The 56 MuSiQue traces routed to `selection` by the E3 rule (`route()` on
`rebuttal/pilots/20261113_main_table_redo/results.json` and its
`population.json`), **score-ranked relay, k = 3**, three base models
(Qwen-235B, GPT-4o-mini, Gemma-4-31B). 14 have a correct original answer, 42
wrong; 55 unique instances.

52 of the 56 have a pool carrier for the first board-absent fact. The other 4
have no pool carrier (a label inconsistency) and are reported as
**unrepairable**; they receive no R-sel arm and are excluded from the contrast.
The 52 tested traces cover 51 unique instances.

## Target and donor

For each tested trace, take the first fact (fact_id order) whose extraction
status is `present` or `partial` and whose board status is `absent`.

- **Target agent**: the agent of the extraction carrier unit, chosen by
  `SHA-256(json([44, instance_id, agent]))` order when several.
- **Target request units**: the extraction carrier `unit_ids` for that fact,
  up to 2 in unit_id order. This is the targeted request; it is not a generic
  retry.
- **Donor**: a board agent with no extraction carrier for any fact, chosen by
  the same SHA order; if none, the non-target board agent by the same order.
- **Donor request units**: the donor's first up-to-2 pool units not on the
  board, in pool order, truncated to the target count. If no donor has the
  target count, the pair is reported as a **no-same-volume control** and is
  excluded from the matched contrast.

## Arms

- **Rerun**: original board, one aggregation call.
- **R-sel**: add the target request units to the board, rerun.
- **V-sel**: add the donor request units, rerun.

52 traces × 3 arms = **156 calls**. Cap **$0.50**; projected about **$0.20**.

## Outcome

Exact match / F1 against the MuSiQue gold answer. Paired contrasts:
R-sel − Rerun and R-sel − V-sel; cluster bootstrap over instances (2,000
draws, seed 42), 95% CIs. Correct-answer cases are reported as a control.
Descriptive; no claim if the pilot fails.

## Pilot

The first 3 tested traces by `SHA-256(json([44, instance_id, model]))` order,
same arms. Pilot outcomes are not used in the final table; pilot cost is on
record. The full run covers all 52 tested traces, including the pilot traces,
under the same frozen rule.