# Full Silo-Bench presence run (main table, presence only)

Rule `FULL_RULE.md` (sha256 `2b196dd2a602`); prompt `labeller_prompt.json` (sha256 `27aca1ccdc8d`); validated on Silo-Bench in `20261113_sb_presence_validation` (24 + 48 cases, combined result in `report_v2.md`). 1087 of 1092 rows scored (5 excluded for output truncation at 4096; see note), spend **$1.256718**, cap $5.00. 3 models x 2 agent counts x 4 protocols; extraction pool and shared board. Old = frozen lexical rule on the same entries; new = per-fact presence label (Claude Haiku 5.5). All coverage figures are **central-claim presence**: measured coverage and critical recall are **upper bounds**, measured omission and loss are **lower bounds**; this is not full sub-claim coverage. Fidelity is not redone and stays unvalidated. **Every new column cell below carries this qualifier.**

| model | protocol | cp | n | CR old-recomp | CR new* | Om old-recomp | Om new* | complete old-recomp | complete new* | AF old-recomp | AF new* |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| mistrals | random_relay | board | 52 | 0.926 | 0.972 | 0.074 | 0.028 | 0.885 | 0.846 | 0.750 | 0.712 |
| mistrals | random_relay | extraction | 52 | 0.926 | 0.977 | 0.074 | 0.023 | 0.885 | 0.885 | 0.750 | 0.731 |
| mistrals | redundancy_aware_relay | board | 52 | 0.926 | 0.977 | 0.074 | 0.023 | 0.885 | 0.885 | 0.731 | 0.750 |
| mistrals | redundancy_aware_relay | extraction | 52 | 0.926 | 0.964 | 0.074 | 0.036 | 0.885 | 0.846 | 0.731 | 0.731 |
| mistrals | score_ranked_relay | board | 52 | 0.926 | 0.969 | 0.074 | 0.031 | 0.885 | 0.846 | 0.750 | 0.769 |
| mistrals | score_ranked_relay | extraction | 52 | 0.926 | 0.972 | 0.074 | 0.028 | 0.885 | 0.865 | 0.750 | 0.750 |
| mistrals | summary_exchange | board | 52 | 0.767 | 0.792 | 0.233 | 0.208 | 0.712 | 0.577 | 0.635 | 0.481 |
| qwen235b | random_relay | board | 52 | 0.879 | 0.987 | 0.121 | 0.013 | 0.865 | 0.981 | 0.712 | 0.827 |
| qwen235b | random_relay | extraction | 52 | 0.879 | 0.992 | 0.121 | 0.008 | 0.865 | 0.981 | 0.712 | 0.827 |
| qwen235b | redundancy_aware_relay | board | 52 | 0.879 | 0.997 | 0.121 | 0.003 | 0.865 | 0.981 | 0.692 | 0.808 |
| qwen235b | redundancy_aware_relay | extraction | 51 | 0.903 | 0.989 | 0.097 | 0.011 | 0.882 | 0.980 | 0.706 | 0.804 |
| qwen235b | score_ranked_relay | board | 52 | 0.879 | 0.959 | 0.121 | 0.041 | 0.865 | 0.942 | 0.692 | 0.788 |
| qwen235b | score_ranked_relay | extraction | 52 | 0.879 | 0.992 | 0.121 | 0.008 | 0.865 | 0.981 | 0.692 | 0.808 |
| qwen235b | summary_exchange | board | 51 | 0.703 | 0.703 | 0.297 | 0.297 | 0.608 | 0.490 | 0.549 | 0.412 |
| qwen36f | random_relay | board | 51 | 0.908 | 1.000 | 0.092 | 0.000 | 0.902 | 1.000 | 0.353 | 0.392 |
| qwen36f | random_relay | extraction | 52 | 0.910 | 0.990 | 0.090 | 0.010 | 0.904 | 0.981 | 0.346 | 0.385 |
| qwen36f | redundancy_aware_relay | board | 51 | 0.908 | 1.000 | 0.092 | 0.000 | 0.902 | 1.000 | 0.333 | 0.392 |
| qwen36f | redundancy_aware_relay | extraction | 51 | 0.908 | 1.000 | 0.092 | 0.000 | 0.902 | 1.000 | 0.333 | 0.392 |
| qwen36f | score_ranked_relay | board | 52 | 0.910 | 1.000 | 0.090 | 0.000 | 0.904 | 1.000 | 0.365 | 0.404 |
| qwen36f | score_ranked_relay | extraction | 52 | 0.910 | 0.997 | 0.090 | 0.003 | 0.904 | 0.981 | 0.365 | 0.404 |
| qwen36f | summary_exchange | board | 52 | 0.726 | 0.805 | 0.274 | 0.195 | 0.692 | 0.577 | 0.500 | 0.327 |

* central-claim presence: CR is an upper bound, omission a lower bound. Published-record reconciliation: the paper's SB CR is the equal-weight n5/n10 lexical mean computed with `get_transmitted_units` at its default `n_agents=5`, so n=10 contributes only agents 0-4 (qwen36f random board: .8038 with 5 agents vs .9231 with all 10; equal-weight mean .8442 = .844). The recomputed old column here uses all 10 board agents and is therefore higher (.908); the paper figures remain the record and the recomputed old is the same-units baseline.


## Published Silo-Bench CR, kept as the record

| protocol | Qwen-235B | Mistral-S | Qwen-3.6-F |
| --- | ---: | ---: | ---: |
| Summary Exchange | .669 | .750 | .725 |
| Random Relay | .844 | .885 | .844 |
| Score-Ranked Relay | .844 | .885 | .844 |
| Redundancy-Aware Relay | .844 | .885 | .844 |

One line: these published figures average n=5 and n=10 lexical CR with agents **0–4 only** on the n=10 runs (`get_transmitted_units` default `n_agents=5`), so they are lower than the all-agent recomp; they stay the record and the recomputed old is the same-units baseline.

## Pooled by checkpoint, 95% CIs (instance-cluster bootstrap, 2,000 draws)

All new-column cells: central-claim presence; CR upper bound, omission lower bound.
**Extraction rows are unvalidated:** the Silo-Bench presence validation covered
the board checkpoint only, and the extraction-specific validations failed
(v3 κ .127, v4 κ .553). Every `extraction` row below is exploratory.

| cp | metric | old [95% CI] | new [95% CI] |
| --- | --- | --- | --- |
| extraction | CR | 0.907 [0.825, 0.972] | 0.986 [0.976, 0.994] |
| extraction | complete | 0.886 [0.807, 0.953] | 0.944 [0.910, 0.976] |
| extraction | AF | 0.599 [0.504, 0.694] | 0.648 [0.559, 0.732] |
| board | CR | 0.862 [0.778, 0.930] | 0.930 [0.909, 0.950] |
| board | complete | 0.831 [0.749, 0.901] | 0.844 [0.800, 0.886] |
| board | AF | 0.589 [0.501, 0.680] | 0.589 [0.512, 0.662] |

## Per-cell 95% CIs (instance-cluster bootstrap, 2,000 draws)

All new-column cells: central-claim presence; CR upper bound, omission lower bound.

| model | protocol | cp | CR old [CI] | CR new [CI] | complete old [CI] | complete new [CI] | AF old [CI] | AF new [CI] |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| mistrals | random_relay | board | 0.926 [0.851, 0.983] | 0.972 [0.951, 0.989] | 0.885 [0.788, 0.962] | 0.846 [0.750, 0.942] | 0.750 [0.635, 0.865] | 0.712 [0.577, 0.827] |
| mistrals | random_relay | extraction | 0.926 [0.851, 0.983] | 0.977 [0.956, 0.993] | 0.885 [0.788, 0.962] | 0.885 [0.788, 0.962] | 0.750 [0.635, 0.865] | 0.731 [0.615, 0.846] |
| mistrals | redundancy_aware_relay | board | 0.926 [0.851, 0.983] | 0.977 [0.956, 0.993] | 0.885 [0.788, 0.962] | 0.885 [0.788, 0.962] | 0.731 [0.615, 0.846] | 0.750 [0.635, 0.865] |
| mistrals | redundancy_aware_relay | extraction | 0.926 [0.851, 0.983] | 0.964 [0.937, 0.987] | 0.885 [0.788, 0.962] | 0.846 [0.750, 0.942] | 0.731 [0.615, 0.846] | 0.731 [0.596, 0.846] |
| mistrals | score_ranked_relay | board | 0.926 [0.851, 0.983] | 0.969 [0.947, 0.989] | 0.885 [0.788, 0.962] | 0.846 [0.750, 0.942] | 0.750 [0.635, 0.865] | 0.769 [0.654, 0.885] |
| mistrals | score_ranked_relay | extraction | 0.926 [0.851, 0.983] | 0.972 [0.948, 0.992] | 0.885 [0.788, 0.962] | 0.865 [0.769, 0.962] | 0.750 [0.635, 0.865] | 0.750 [0.635, 0.865] |
| mistrals | summary_exchange | board | 0.767 [0.644, 0.874] | 0.792 [0.700, 0.876] | 0.712 [0.596, 0.827] | 0.577 [0.442, 0.712] | 0.635 [0.500, 0.769] | 0.481 [0.346, 0.615] |
| qwen235b | random_relay | board | 0.879 [0.785, 0.962] | 0.987 [0.960, 1.000] | 0.865 [0.769, 0.942] | 0.981 [0.942, 1.000] | 0.712 [0.596, 0.827] | 0.827 [0.712, 0.923] |
| qwen235b | random_relay | extraction | 0.879 [0.785, 0.962] | 0.992 [0.976, 1.000] | 0.865 [0.769, 0.942] | 0.981 [0.942, 1.000] | 0.712 [0.596, 0.827] | 0.827 [0.712, 0.923] |
| qwen235b | redundancy_aware_relay | board | 0.879 [0.785, 0.962] | 0.997 [0.992, 1.000] | 0.865 [0.769, 0.942] | 0.981 [0.942, 1.000] | 0.692 [0.577, 0.808] | 0.808 [0.692, 0.904] |
| qwen235b | redundancy_aware_relay | extraction | 0.903 [0.812, 0.974] | 0.989 [0.967, 1.000] | 0.882 [0.784, 0.961] | 0.980 [0.941, 1.000] | 0.706 [0.569, 0.824] | 0.804 [0.686, 0.902] |
| qwen235b | score_ranked_relay | board | 0.879 [0.785, 0.962] | 0.959 [0.901, 1.000] | 0.865 [0.769, 0.942] | 0.942 [0.865, 1.000] | 0.692 [0.577, 0.808] | 0.788 [0.673, 0.904] |
| qwen235b | score_ranked_relay | extraction | 0.879 [0.785, 0.962] | 0.992 [0.976, 1.000] | 0.865 [0.769, 0.942] | 0.981 [0.942, 1.000] | 0.692 [0.577, 0.808] | 0.808 [0.692, 0.904] |
| qwen235b | summary_exchange | board | 0.703 [0.574, 0.820] | 0.703 [0.603, 0.803] | 0.608 [0.471, 0.745] | 0.490 [0.353, 0.627] | 0.549 [0.412, 0.686] | 0.412 [0.294, 0.549] |
| qwen36f | random_relay | board | 0.908 [0.815, 0.975] | 1.000 [1.000, 1.000] | 0.902 [0.804, 0.980] | 1.000 [1.000, 1.000] | 0.353 [0.216, 0.471] | 0.392 [0.255, 0.529] |
| qwen36f | random_relay | extraction | 0.910 [0.821, 0.976] | 0.990 [0.967, 1.000] | 0.904 [0.827, 0.981] | 0.981 [0.942, 1.000] | 0.346 [0.231, 0.481] | 0.385 [0.250, 0.519] |
| qwen36f | redundancy_aware_relay | board | 0.908 [0.815, 0.975] | 1.000 [1.000, 1.000] | 0.902 [0.804, 0.980] | 1.000 [1.000, 1.000] | 0.333 [0.216, 0.471] | 0.392 [0.275, 0.529] |
| qwen36f | redundancy_aware_relay | extraction | 0.908 [0.815, 0.975] | 1.000 [1.000, 1.000] | 0.902 [0.804, 0.980] | 1.000 [1.000, 1.000] | 0.333 [0.216, 0.471] | 0.392 [0.275, 0.529] |
| qwen36f | score_ranked_relay | board | 0.910 [0.821, 0.976] | 1.000 [1.000, 1.000] | 0.904 [0.827, 0.981] | 1.000 [1.000, 1.000] | 0.365 [0.250, 0.500] | 0.404 [0.269, 0.538] |
| qwen36f | score_ranked_relay | extraction | 0.910 [0.821, 0.976] | 0.997 [0.992, 1.000] | 0.904 [0.827, 0.981] | 0.981 [0.942, 1.000] | 0.365 [0.250, 0.500] | 0.404 [0.269, 0.538] |
| qwen36f | summary_exchange | board | 0.726 [0.600, 0.848] | 0.805 [0.718, 0.886] | 0.692 [0.577, 0.808] | 0.577 [0.442, 0.712] | 0.500 [0.365, 0.635] | 0.327 [0.212, 0.462] |

Every coverage figure is **central-claim presence; lower bound on loss and omission**. The label was validated on Silo-Bench board cases against Gemini 3.6 Flash, not author ground truth; the combined validation kappa is **.653 [.447, .854]** on 69 cases, still a wide interval, and the point-estimate PASS is not a precise reliability claim. The label was validated on **board** cases; the extraction column uses the same label but was not separately validated there. No fidelity number is reported here.

