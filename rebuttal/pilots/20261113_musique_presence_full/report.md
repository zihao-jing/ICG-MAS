# Full MuSiQue presence run (main table, presence only)

Rule `FULL_RULE.md` (sha256 `394c7cd641ee`); prompt `per_fact_prompt_v9.json` (sha256 `f518c16a65c6`); 3 models x 100 instances x 4 protocols x checkpoints = 2100 calls, spend $1.422365, cap $5.00. Stage: relay checkpoints. Old = frozen lexical rule on the same traces; new = V9 per-fact presence label (Claude Haiku 5.5), validated on MuSiQue only. Fidelity/Dist is not redone here and stays unvalidated. **Every new coverage cell below is central-claim presence: measured coverage and critical recall are upper bounds, measured loss and omission are lower bounds; not full sub-claim coverage.**

| model | protocol | cp | n | CR old | CR new* | Om old | Om new* | complete old | complete new* | AF old | AF new* |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |

* central-claim presence: CR is an upper bound, omission a lower bound.
| mistrals | random_relay | board | 100 | 1.000 | 0.879 | 0.000 | 0.121 | 1.000 | 0.690 | 0.790 | 0.530 |
| mistrals | random_relay | extraction | 100 | 1.000 | 0.883 | 0.000 | 0.117 | 1.000 | 0.700 | 0.790 | 0.540 |
| mistrals | redundancy_aware_relay | board | 100 | 1.000 | 0.879 | 0.000 | 0.121 | 1.000 | 0.690 | 0.790 | 0.530 |
| mistrals | redundancy_aware_relay | extraction | 100 | 1.000 | 0.879 | 0.000 | 0.121 | 1.000 | 0.690 | 0.790 | 0.530 |
| mistrals | score_ranked_relay | board | 100 | 1.000 | 0.879 | 0.000 | 0.121 | 1.000 | 0.690 | 0.820 | 0.540 |
| mistrals | score_ranked_relay | extraction | 100 | 1.000 | 0.887 | 0.000 | 0.113 | 1.000 | 0.710 | 0.820 | 0.550 |
| mistrals | summary_exchange | board | 100 | 1.000 | 0.811 | 0.000 | 0.189 | 1.000 | 0.540 | 0.760 | 0.380 |
| qwen235b | random_relay | board | 100 | 1.000 | 0.902 | 0.000 | 0.098 | 1.000 | 0.770 | 0.720 | 0.520 |
| qwen235b | random_relay | extraction | 100 | 1.000 | 0.898 | 0.000 | 0.102 | 1.000 | 0.750 | 0.720 | 0.500 |
| qwen235b | redundancy_aware_relay | board | 100 | 1.000 | 0.906 | 0.000 | 0.094 | 1.000 | 0.770 | 0.720 | 0.520 |
| qwen235b | redundancy_aware_relay | extraction | 100 | 1.000 | 0.906 | 0.000 | 0.094 | 1.000 | 0.770 | 0.720 | 0.530 |
| qwen235b | score_ranked_relay | board | 100 | 1.000 | 0.906 | 0.000 | 0.094 | 1.000 | 0.770 | 0.680 | 0.500 |
| qwen235b | score_ranked_relay | extraction | 100 | 1.000 | 0.906 | 0.000 | 0.094 | 1.000 | 0.770 | 0.680 | 0.500 |
| qwen235b | summary_exchange | board | 100 | 1.000 | 0.879 | 0.000 | 0.121 | 1.000 | 0.720 | 0.790 | 0.540 |
| qwen36f | random_relay | board | 100 | 1.000 | 0.955 | 0.000 | 0.045 | 1.000 | 0.890 | 0.530 | 0.500 |
| qwen36f | random_relay | extraction | 100 | 1.000 | 0.947 | 0.000 | 0.053 | 1.000 | 0.860 | 0.530 | 0.460 |
| qwen36f | redundancy_aware_relay | board | 100 | 1.000 | 0.951 | 0.000 | 0.049 | 1.000 | 0.870 | 0.510 | 0.460 |
| qwen36f | redundancy_aware_relay | extraction | 100 | 1.000 | 0.951 | 0.000 | 0.049 | 1.000 | 0.880 | 0.510 | 0.450 |
| qwen36f | score_ranked_relay | board | 100 | 1.000 | 0.943 | 0.000 | 0.057 | 1.000 | 0.860 | 0.480 | 0.410 |
| qwen36f | score_ranked_relay | extraction | 100 | 1.000 | 0.955 | 0.000 | 0.045 | 1.000 | 0.880 | 0.480 | 0.430 |
| qwen36f | summary_exchange | board | 100 | 1.000 | 0.928 | 0.000 | 0.072 | 1.000 | 0.810 | 0.650 | 0.520 |

## Pooled by checkpoint, 95% CIs (instance-cluster bootstrap, 2,000 draws)

All new-column cells: central-claim presence; CR upper bound, omission lower bound.

| cp | metric | old [95% CI] | new [95% CI] |
| --- | --- | --- | --- |
| extraction | CR | 1.000 [1.000, 1.000] | 0.912 [0.888, 0.935] |
| extraction | complete | 1.000 [1.000, 1.000] | 0.779 [0.716, 0.838] |
| extraction | AF | 0.671 [0.602, 0.737] | 0.499 [0.426, 0.569] |
| board | CR | 1.000 [1.000, 1.000] | 0.902 [0.878, 0.922] |
| board | complete | 1.000 [1.000, 1.000] | 0.756 [0.698, 0.811] |
| board | AF | 0.687 [0.621, 0.750] | 0.496 [0.428, 0.562] |

**Reconciliation note (2026-11-14).** Recount from `results.json` using the same
definition as the report (present + partial over all facts): extraction
2,176/2,385 = .91237; board 2,867/3,180 = .90157; board complete 907/1,200
traces = .75583. Instance-cluster bootstrap over instances, 2,000 draws, seed
43, percentile interval: extraction CR [.88759, .93529]; board CR [.87825,
.92241]; board complete [.69750, .81083]. Standard rounding to three decimals
gives .888/.902/.698, which is what the printed rows above, the batch 2 report
and the final text now use. The source records and the batch 2 report agree; no
discrepancy remains.

## Per-cell 95% CIs (instance-cluster bootstrap, 2,000 draws)

All new-column cells: central-claim presence; CR upper bound, omission lower bound.

| model | protocol | cp | CR old [CI] | CR new [CI] | complete old [CI] | complete new [CI] | AF old [CI] | AF new [CI] |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| mistrals | random_relay | board | 1.000 [1.000, 1.000] | 0.879 [0.844, 0.913] | 1.000 [1.000, 1.000] | 0.690 [0.600, 0.780] | 0.790 [0.710, 0.860] | 0.530 [0.430, 0.630] |
| mistrals | random_relay | extraction | 1.000 [1.000, 1.000] | 0.883 [0.847, 0.916] | 1.000 [1.000, 1.000] | 0.700 [0.600, 0.790] | 0.790 [0.710, 0.860] | 0.540 [0.440, 0.640] |
| mistrals | redundancy_aware_relay | board | 1.000 [1.000, 1.000] | 0.879 [0.845, 0.914] | 1.000 [1.000, 1.000] | 0.690 [0.600, 0.780] | 0.790 [0.710, 0.860] | 0.530 [0.430, 0.620] |
| mistrals | redundancy_aware_relay | extraction | 1.000 [1.000, 1.000] | 0.879 [0.843, 0.913] | 1.000 [1.000, 1.000] | 0.690 [0.590, 0.780] | 0.790 [0.710, 0.860] | 0.530 [0.430, 0.620] |
| mistrals | score_ranked_relay | board | 1.000 [1.000, 1.000] | 0.879 [0.844, 0.913] | 1.000 [1.000, 1.000] | 0.690 [0.600, 0.780] | 0.820 [0.750, 0.890] | 0.540 [0.440, 0.630] |
| mistrals | score_ranked_relay | extraction | 1.000 [1.000, 1.000] | 0.887 [0.851, 0.920] | 1.000 [1.000, 1.000] | 0.710 [0.620, 0.790] | 0.820 [0.750, 0.890] | 0.550 [0.450, 0.640] |
| mistrals | summary_exchange | board | 1.000 [1.000, 1.000] | 0.811 [0.772, 0.851] | 1.000 [1.000, 1.000] | 0.540 [0.450, 0.640] | 0.760 [0.670, 0.840] | 0.380 [0.280, 0.470] |
| qwen235b | random_relay | board | 1.000 [1.000, 1.000] | 0.902 [0.864, 0.935] | 1.000 [1.000, 1.000] | 0.770 [0.690, 0.850] | 0.720 [0.630, 0.800] | 0.520 [0.420, 0.610] |
| qwen235b | random_relay | extraction | 1.000 [1.000, 1.000] | 0.898 [0.862, 0.933] | 1.000 [1.000, 1.000] | 0.750 [0.660, 0.830] | 0.720 [0.630, 0.800] | 0.500 [0.400, 0.600] |
| qwen235b | redundancy_aware_relay | board | 1.000 [1.000, 1.000] | 0.906 [0.871, 0.938] | 1.000 [1.000, 1.000] | 0.770 [0.690, 0.850] | 0.720 [0.630, 0.800] | 0.520 [0.420, 0.620] |
| qwen235b | redundancy_aware_relay | extraction | 1.000 [1.000, 1.000] | 0.906 [0.870, 0.938] | 1.000 [1.000, 1.000] | 0.770 [0.680, 0.850] | 0.720 [0.630, 0.800] | 0.530 [0.430, 0.630] |
| qwen235b | score_ranked_relay | board | 1.000 [1.000, 1.000] | 0.906 [0.869, 0.938] | 1.000 [1.000, 1.000] | 0.770 [0.690, 0.850] | 0.680 [0.590, 0.770] | 0.500 [0.400, 0.590] |
| qwen235b | score_ranked_relay | extraction | 1.000 [1.000, 1.000] | 0.906 [0.871, 0.937] | 1.000 [1.000, 1.000] | 0.770 [0.690, 0.850] | 0.680 [0.590, 0.770] | 0.500 [0.400, 0.600] |
| qwen235b | summary_exchange | board | 1.000 [1.000, 1.000] | 0.879 [0.841, 0.918] | 1.000 [1.000, 1.000] | 0.720 [0.630, 0.810] | 0.790 [0.710, 0.870] | 0.540 [0.450, 0.640] |
| qwen36f | random_relay | board | 1.000 [1.000, 1.000] | 0.955 [0.927, 0.978] | 1.000 [1.000, 1.000] | 0.890 [0.820, 0.950] | 0.530 [0.430, 0.620] | 0.500 [0.400, 0.600] |
| qwen36f | random_relay | extraction | 1.000 [1.000, 1.000] | 0.947 [0.919, 0.972] | 1.000 [1.000, 1.000] | 0.860 [0.790, 0.930] | 0.530 [0.430, 0.620] | 0.460 [0.360, 0.560] |
| qwen36f | redundancy_aware_relay | board | 1.000 [1.000, 1.000] | 0.951 [0.924, 0.974] | 1.000 [1.000, 1.000] | 0.870 [0.800, 0.930] | 0.510 [0.410, 0.610] | 0.460 [0.360, 0.560] |
| qwen36f | redundancy_aware_relay | extraction | 1.000 [1.000, 1.000] | 0.951 [0.922, 0.977] | 1.000 [1.000, 1.000] | 0.880 [0.810, 0.940] | 0.510 [0.410, 0.610] | 0.450 [0.350, 0.550] |
| qwen36f | score_ranked_relay | board | 1.000 [1.000, 1.000] | 0.943 [0.914, 0.970] | 1.000 [1.000, 1.000] | 0.860 [0.790, 0.920] | 0.480 [0.380, 0.580] | 0.410 [0.310, 0.510] |
| qwen36f | score_ranked_relay | extraction | 1.000 [1.000, 1.000] | 0.955 [0.929, 0.978] | 1.000 [1.000, 1.000] | 0.880 [0.810, 0.940] | 0.480 [0.380, 0.580] | 0.430 [0.330, 0.530] |
| qwen36f | summary_exchange | board | 1.000 [1.000, 1.000] | 0.928 [0.898, 0.956] | 1.000 [1.000, 1.000] | 0.810 [0.730, 0.880] | 0.650 [0.550, 0.740] | 0.520 [0.430, 0.620] |

No fidelity number is reported here. The Silo-Bench presence label was validated separately (report in `20261113_sb_presence_validation`); its rows are not part of this MuSiQue run. All coverage figures are **central-claim presence**, not full sub-claim coverage: the ceiling check found sub-claims missing in 10/10 checked cases.

