# Proxy presence at atom level vs gold stage

2026-11-15. Rule `Proxy-atom-presence.md` (sha `3f46ca1d...`). Labeller: Claude Haiku 5.5 with the validated atom-level point prompt v1 (sha `86d84ff6...`), the same model as the gold labeller and the stored proxy checkpoint labels (which used the fact-level prompt v3). 31 unique random_relay traces; $0.028124, cap $0.30.

Calls: 72 facts x 2 checkpoints = 144 result calls, 0 skipped at the cap, no retries. The trace counts below are per sample and the samples overlap (13 + 11 + 15 = 39 scores over 31 unique traces), so they are not multiplied by two checkpoints.

| sample | both stages | agree | rate [95% Wilson] | no atom stage |
| --- | ---: | ---: | --- | ---: |
| sample1_uniform | 13 | 3 | 0.231 [0.082, 0.503] | 0 |
| sample2_coarse | 11 | 2 | 0.182 [0.051, 0.477] | 0 |
| sample3_atom | 15 | 4 | 0.267 [0.109, 0.520] | 0 |

## Confusion, atom-level proxy stage (rows) by gold stage (columns)

### sample1_uniform

| proxy \ gold | extraction | transmission | aggregation |
| --- | ---: | ---: | ---: |
| extraction | 1 | 0 | 1 |
| transmission | 1 | 0 | 0 |
| aggregation | 8 | 0 | 2 |

### sample2_coarse

| proxy \ gold | extraction | transmission | aggregation |
| --- | ---: | ---: | ---: |
| extraction | 1 | 0 | 1 |
| transmission | 0 | 0 | 0 |
| aggregation | 8 | 0 | 1 |

### sample3_atom

| proxy \ gold | extraction | transmission | aggregation |
| --- | ---: | ---: | ---: |
| extraction | 1 | 0 | 1 |
| transmission | 1 | 0 | 0 |
| aggregation | 9 | 0 | 3 |

