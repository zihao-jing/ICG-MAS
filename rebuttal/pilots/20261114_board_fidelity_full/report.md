# Board strict-fidelity full run

Rule `RUN_RULE.md` (sha256 `f35c37de07a4`); prompt `per_fact_prompt_v10.json` (sha256 `94ade327ceea`); Claude Opus 5.5, max 2500, reasoning. 1824 of 1824 rows labelled (0 excluded after 3 attempts); 7860 fact labels; spend **$39.755868**, staged at $5 per invocation. Stage: shared board.

Pre-run projection was **$43.92** (MuSiQue $21.59, Silo-Bench $22.34). Full-run spend is **$39.755868**; with the pilot's $4.033836 the total is **$43.789704**, within the $50 stop line.

| fidelity | facts |
| --- | ---: |
| faithful | 6265 |
| partial | 890 |
| distorted | 178 |
| absent | 527 |

## Faithful rate by cell

| benchmark | model | protocol | rows | facts | faithful | rate |
| --- | --- | --- | ---: | ---: | ---: | ---: |
| musique | mistrals | random_relay | 100 | 265 | 220 | 0.830 |
| musique | mistrals | redundancy_aware_relay | 100 | 265 | 220 | 0.830 |
| musique | mistrals | score_ranked_relay | 100 | 265 | 220 | 0.830 |
| musique | mistrals | summary_exchange | 100 | 265 | 188 | 0.709 |
| musique | qwen235b | random_relay | 100 | 265 | 233 | 0.879 |
| musique | qwen235b | redundancy_aware_relay | 100 | 265 | 234 | 0.883 |
| musique | qwen235b | score_ranked_relay | 100 | 265 | 233 | 0.879 |
| musique | qwen235b | summary_exchange | 100 | 265 | 212 | 0.800 |
| musique | qwen36f | random_relay | 100 | 265 | 239 | 0.902 |
| musique | qwen36f | redundancy_aware_relay | 100 | 265 | 239 | 0.902 |
| musique | qwen36f | score_ranked_relay | 100 | 265 | 240 | 0.906 |
| musique | qwen36f | summary_exchange | 100 | 265 | 238 | 0.898 |
| silobench | mistrals | random_relay | 52 | 390 | 352 | 0.903 |
| silobench | mistrals | redundancy_aware_relay | 52 | 390 | 349 | 0.895 |
| silobench | mistrals | score_ranked_relay | 52 | 390 | 353 | 0.905 |
| silobench | mistrals | summary_exchange | 52 | 390 | 188 | 0.482 |
| silobench | qwen235b | random_relay | 52 | 390 | 294 | 0.754 |
| silobench | qwen235b | redundancy_aware_relay | 52 | 390 | 301 | 0.772 |
| silobench | qwen235b | score_ranked_relay | 52 | 390 | 295 | 0.756 |
| silobench | qwen235b | summary_exchange | 52 | 390 | 131 | 0.336 |
| silobench | qwen36f | random_relay | 52 | 390 | 363 | 0.931 |
| silobench | qwen36f | redundancy_aware_relay | 52 | 390 | 363 | 0.931 |
| silobench | qwen36f | score_ranked_relay | 52 | 390 | 364 | 0.933 |
| silobench | qwen36f | summary_exchange | 52 | 390 | 196 | 0.503 |

## Validation caveats

- Natural board cases (V10): **158/163 = .969 [.930, .990]**, kappa **.721 [.429, .930]**.
- Constructed distortions, all 37: **.946 [.818, .993]**, kappa **.641**; the constructed interval is **wide**.
- Secondary "distorted vs not" on constructed cases: **.865**, kappa **.467**; **Dist stays unvalidated**.

Every fidelity cell carries these caveats: the label is validated on natural board cases at kappa .721 [.429, .930], the constructed interval is wide, and Dist is unvalidated. Coverage/CR remain upper bounds, loss/omission lower bounds where presence is reported.

