# Answer-equivalence check: Silo-Bench only

Prompt `answer-equiv-v1` (file sha256 `51082bc881a19231299de0e9fab4e574895760637276abce7845294b9eec8153`). Qwen-235B, Silo-Bench 52 traces, four protocols; scored 208/208; spend $0.083332 in total, including the 100 MuSiQue calls that are logged but not used here, against a $2 cap.

Validation on the 150 author-labelled traces: agreement 0.940, kappa 0.848 (95% CI 0.725-0.939), EQUIVALENT recall 0.947; the frozen gate (kappa >= 0.75 on the point estimate) passed.

The check is reported only for Silo-Bench. The MuSiQue cells stay at lexical exact/F1: the check was not validated on MuSiQue-style free-text answers, and on this population it is much more permissive than lexical. The 100 MuSiQue calls were made and are logged, but their cells are not reported here and do not replace the lexical cells.

| cell | n | paper cell (SB exact) | lexical exact | answer-equiv |
| --- | ---: | ---: | ---: | ---: |
| SB summary_exchange | 52 | 9.6% | 9.6% | 11.5% |
| SB random_relay | 52 | 17.3% | 17.3% | 17.3% |
| SB score_ranked_relay | 52 | 19.2% | 19.2% | 19.2% |
| SB redundancy_aware_relay | 52 | 19.2% | 19.2% | 19.2% |
| **SB pooled** | 208 | 16.3% | 16.3% | 16.8% |

## Agreement on Silo-Bench

Answer-equivalence vs lexical exact match: 207/208 (99.5%); kappa 0.983.
The check moves one SB summary trace from wrong to right (one disagreement, lexical wrong / check EQUIVALENT); no SB answer that lexical scores right is called not-equivalent.

1 disagreements are listed in `main_tables_summary.json`.
