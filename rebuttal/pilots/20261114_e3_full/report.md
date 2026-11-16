# E3 full: checkpoint-removal route counts

Rule `rebuttal/pilots/prereg/E3-pilot.md` (sha256 `eac31aa38de1`), frozen before the run. 2395 traces (5 no-fact traces excluded from 2400); 0 model calls, $0.00. Stage: audit routing checkpoints (extraction pool, board fidelity, aggregation). Descriptive only.

**Labels.** Extraction presence (prompt v3) is validated on MuSiQue: 60 fresh traces, 176 facts, agreement .915 [.863, .952], kappa .780 [.665, .877], against a frozen Gemini reference. Silo-Bench extraction **fails** (30 traces, 250 facts, agreement .860 [.811, .901], kappa .127 [0, .270]) and this run has no Silo-Bench traces (all 2,395 are MuSiQue), so no Silo-Bench row is reported. Board carrier identification is validated at .881 [.823, .925], MuSiQue, cross-model. Fidelity/distortion labels remain unvalidated.

The presence label **over-credits in all disagreements** (MuSiQue 15 over-credits, 0 misses; Silo-Bench 35 over-credits, 0 misses). It is lenient, so extraction loss counts are lower bounds.

## Full route

| route | n |
|---|---:|
| aggregation | 789 |
| correct | 665 |
| distortion | 148 |
| extraction | 737 |
| selection | 56 |

## Routes changed when a check is removed

| removed | changed | share [95% CI] | route changes |
|---|---:|---|---|
| pool | 737/2395 | 0.308 [0.290, 0.327] | extraction->aggregation (31), extraction->correct (18), extraction->distortion (13), extraction->selection (675) |
| fidelity | 148/2395 | 0.062 [0.053, 0.072] | distortion->aggregation (93), distortion->correct (55) |
| aggregation | 789/2395 | 0.329 [0.311, 0.349] | aggregation->correct (789) |
| all_three | 2395/2395 | 1.000 [0.998, 1.000] | aggregation->unrouted (789), correct->unrouted (665), distortion->unrouted (148), extraction->unrouted (737), selection->unrouted (56) |

The pool row is **definitional**: `route()` assigns `extraction` exactly when the pool check finds a required fact absent, so removing the check moves every extraction-routed trace and no other. The fidelity row is likewise exactly the traces the fidelity check routes to `distortion`.
