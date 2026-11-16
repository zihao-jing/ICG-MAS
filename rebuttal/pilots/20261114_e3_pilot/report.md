# E3 pilot: checkpoint-removal route counts

Rule `rebuttal/pilots/prereg/E3-pilot.md` (sha256 `eac31aa38de1`), frozen before the run. 50 traces (5 no-fact traces excluded from 2400); 0 model calls, $0.00. Stage: audit routing checkpoints (extraction pool, board fidelity, aggregation). Descriptive only.

## Full route

| route | n |
|---|---:|
| aggregation | 17 |
| correct | 11 |
| distortion | 3 |
| extraction | 19 |

## Routes changed when a check is removed

| removed | changed | share [95% CI] | route changes |
|---|---:|---|---|
| pool | 19/50 | 0.380 [0.259, 0.518] | extraction->aggregation (1), extraction->selection (18) |
| fidelity | 3/50 | 0.060 [0.021, 0.162] | distortion->aggregation (2), distortion->correct (1) |
| aggregation | 17/50 | 0.340 [0.224, 0.478] | aggregation->correct (17) |
| all_three | 50/50 | 1.000 [0.929, 1.000] | aggregation->unrouted (17), correct->unrouted (11), distortion->unrouted (3), extraction->unrouted (19) |
