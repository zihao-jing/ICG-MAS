# Redundancy rerun with the paper's LLM relevance scorer (frozen before any call)

2026-11-15. Cap **$0.20**. One run, replacing the lexical relevance score used in the rebuild with the paper's
scoring prompt and the paper's model.

## Population and units

The 30 MuSiQue traces and their re-extracted units (`20261115_redundancy/rebuild_units.json`, at most five units
per agent). No re-extraction.

## Scorer

`_SCORING_SYSTEM` from `src/protocols/relay.py` unchanged, on `qwen/qwen3-235b-a22b-2507` (the paper's model and
the model whose protocol runs the paper reports), temperature 0, one call per unit. The reply must parse as a JSON
object containing at least `overall`; otherwise the unit gets the paper's default 0.5 and the call is marked failed.

## Selection

k = 3 per agent, the paper's three protocols: random (seed 43), score-ranked (top 3 by `overall`), and
redundancy-aware (`_redundancy_select`, rho = .5, lexical Jaccard penalty on pairwise unit similarity). Transmitted
units are the selections across agents.

## Metrics and interval

RedundancyRate = mean pairwise Jaccard similarity of transmitted units; UsefulBudget = distinct best-matched gold
support texts / transmitted units, using the paper-definition code (`redundancy_paperdef.py`). Per protocol: mean
over the 30 traces, instance bootstrap 95% interval, 2,000 draws, seed 43. Crowding-out: useful budget by
redundancy quartile.

## Decision rule

If the three protocols' Red intervals overlap, the text states that no protection effect is shown and uses the
paper's Red/UB figures. No further attempts.