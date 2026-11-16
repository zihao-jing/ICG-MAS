# Full sub-claim presence rule B (MuSiQue, stricter column)

Rule `VALIDATION_RULE.md` (sha256 `84bbd35007e8`); B passed the fresh-case validation before this run: 139/144 = .965 [.921, .989], kappa .881 [.748, .978] on 59 fresh board cases (spend $0.889705; the A-complete stratum has kappa ~0 from prevalence). Prompt `subclaim_prompt.json`; Claude Haiku 5.5, max 8192. 2098 of 2100 rows labelled (2 excluded: the model omitted a fact twice); spend **$2.954090**, cap $5.00. Stage: relay checkpoints. A = validated central-claim label; B = sub-claim label. **A is not replaced.** For both columns, coverage and critical recall are upper bounds; loss and omission are lower bounds.

| model | protocol | cp | n | A CR | B CR | A complete | B complete |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: |
| mistrals | random_relay | board | 100 | 0.879 | 0.819 | 0.690 | 0.560 |
| mistrals | random_relay | extraction | 100 | 0.883 | 0.819 | 0.700 | 0.570 |
| mistrals | redundancy_aware_relay | board | 100 | 0.879 | 0.834 | 0.690 | 0.620 |
| mistrals | redundancy_aware_relay | extraction | 100 | 0.879 | 0.823 | 0.690 | 0.590 |
| mistrals | score_ranked_relay | board | 99 | 0.878 | 0.817 | 0.687 | 0.586 |
| mistrals | score_ranked_relay | extraction | 99 | 0.885 | 0.821 | 0.707 | 0.566 |
| mistrals | summary_exchange | board | 100 | 0.811 | 0.709 | 0.540 | 0.390 |
| qwen235b | random_relay | board | 100 | 0.902 | 0.834 | 0.770 | 0.630 |
| qwen235b | random_relay | extraction | 100 | 0.898 | 0.830 | 0.750 | 0.650 |
| qwen235b | redundancy_aware_relay | board | 100 | 0.906 | 0.834 | 0.770 | 0.620 |
| qwen235b | redundancy_aware_relay | extraction | 100 | 0.906 | 0.834 | 0.770 | 0.630 |
| qwen235b | score_ranked_relay | board | 100 | 0.906 | 0.853 | 0.770 | 0.650 |
| qwen235b | score_ranked_relay | extraction | 100 | 0.906 | 0.842 | 0.770 | 0.650 |
| qwen235b | summary_exchange | board | 100 | 0.879 | 0.777 | 0.720 | 0.490 |
| qwen36f | random_relay | board | 100 | 0.955 | 0.860 | 0.890 | 0.690 |
| qwen36f | random_relay | extraction | 100 | 0.947 | 0.868 | 0.860 | 0.700 |
| qwen36f | redundancy_aware_relay | board | 100 | 0.951 | 0.875 | 0.870 | 0.720 |
| qwen36f | redundancy_aware_relay | extraction | 100 | 0.951 | 0.864 | 0.880 | 0.690 |
| qwen36f | score_ranked_relay | board | 100 | 0.943 | 0.853 | 0.860 | 0.650 |
| qwen36f | score_ranked_relay | extraction | 100 | 0.955 | 0.853 | 0.880 | 0.680 |
| qwen36f | summary_exchange | board | 100 | 0.928 | 0.860 | 0.810 | 0.660 |

## Pooled by checkpoint, 95% CIs (instance-cluster bootstrap, 2,000 draws)

| cp | metric | A [95% CI] | B [95% CI] |
| --- | --- | --- | --- |
| extraction | CR | 0.912 [0.887, 0.935] | 0.839 [0.801, 0.873] |
| extraction | complete | 0.779 [0.716, 0.838] | 0.636 [0.561, 0.712] |
| board | CR | 0.901 [0.878, 0.922] | 0.827 [0.794, 0.857] |
| board | complete | 0.756 [0.697, 0.811] | 0.606 [0.536, 0.674] |

B is stricter by construction (it requires every sub-claim), so B CR <= A CR. The A label stays the validated table label with the central-claim qualifier; B is reported beside it. No full-coverage claim is made for either.

