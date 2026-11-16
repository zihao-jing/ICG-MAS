# Redundancy injection at k = 1 and k = 3, v2 — frozen before any call

2026-11-15. Cap **$2.00 per budget** (k = 1 and k = 3 are separate runs). Extends `Redundancy-injection-v1.md` (k = 2, unchanged)
to the other two message budgets. Same population, conditions, protocols, verification and outcome as v1; only k differs.

## Population

Identical to v1: the same 90 cases (first 30 eligible instances per model, `Injection-v1.md` order). No case added or removed.

## Budget and selection

- k = 1 (run A) or k = 3 (run B) units per agent. Each agent's pool holds its stored units (K = 3) with stored scores.
- Score-ranked selection: top k by stored score, ties in stored order.
- Redundancy-aware selection: `_redundancy_select` (src/protocols/relay.py), rho = 0.5, the given k.

## Conditions, verification and outcome

Base and duplicated conditions exactly as v1. Verification as v1 (duplicate present in each duplicated pool; one hand-checked
trace printed; duplicate selection counted). Outcome: answer F1 against gold after the unchanged aggregation prompt and model
(primary). The lexical "gold string in board" column is **dropped** in v2 (validated board presence labels are not run here).
Per protocol and condition: count with F1 = 1.0 with Wilson 95%; mean F1; paired duplicated-minus-base drop/rise/unchanged.

## Calls

One aggregation call per case, condition and protocol: 90 x 2 x 2 = 360 calls per budget. Logged in `calls.jsonl`
with cost. Stops at the cap.
