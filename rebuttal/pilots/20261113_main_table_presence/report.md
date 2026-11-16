# Piece 2 pilot: presence-based main-table columns

Rule `PILOT_RULE.md` (sha256 `cfa082a45653`); prompt `per_fact_prompt_v9.json` (sha256 `f518c16a65c6`); 126 pilot calls, spend $0.173062, cap $5.00. Stage: relay checkpoints (extraction and board). New labels are the V9 per-fact presence label (Claude Haiku 5.5); old labels are the frozen lexical rule on the same traces. Fidelity is **not** redone here and is marked unvalidated.

| model | benchmark | protocol | cp | n | CR old | CR new | Om old | Om new | complete old | complete new | AF old | AF new |
| --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| mistrals | musique | random_relay | board | 2 | 1.000 | 1.000 | 0.000 | 0.000 | 1.000 | 1.000 | 0.500 | 0.500 |
| mistrals | musique | random_relay | extraction | 2 | 1.000 | 1.000 | 0.000 | 0.000 | 1.000 | 1.000 | 0.500 | 0.500 |
| mistrals | musique | redundancy_aware_relay | board | 2 | 1.000 | 1.000 | 0.000 | 0.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| mistrals | musique | redundancy_aware_relay | extraction | 2 | 1.000 | 1.000 | 0.000 | 0.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| mistrals | musique | score_ranked_relay | board | 2 | 1.000 | 1.000 | 0.000 | 0.000 | 1.000 | 1.000 | 0.500 | 0.500 |
| mistrals | musique | score_ranked_relay | extraction | 2 | 1.000 | 1.000 | 0.000 | 0.000 | 1.000 | 1.000 | 0.500 | 0.500 |
| mistrals | musique | summary_exchange | board | 2 | 1.000 | 1.000 | 0.000 | 0.000 | 1.000 | 1.000 | 0.500 | 0.500 |
| mistrals | silobench | random_relay | board | 4 | 0.800 | 1.000 | 0.200 | 0.000 | 0.750 | 1.000 | 0.500 | 0.500 |
| mistrals | silobench | random_relay | extraction | 4 | 0.800 | 1.000 | 0.200 | 0.000 | 0.750 | 1.000 | 0.500 | 0.500 |
| mistrals | silobench | redundancy_aware_relay | board | 4 | 0.800 | 1.000 | 0.200 | 0.000 | 0.750 | 1.000 | 0.500 | 0.750 |
| mistrals | silobench | redundancy_aware_relay | extraction | 4 | 0.800 | 1.000 | 0.200 | 0.000 | 0.750 | 1.000 | 0.500 | 0.750 |
| mistrals | silobench | score_ranked_relay | board | 4 | 0.800 | 1.000 | 0.200 | 0.000 | 0.750 | 1.000 | 0.500 | 0.750 |
| mistrals | silobench | score_ranked_relay | extraction | 4 | 0.800 | 1.000 | 0.200 | 0.000 | 0.750 | 1.000 | 0.500 | 0.750 |
| mistrals | silobench | summary_exchange | board | 4 | 0.750 | 0.775 | 0.250 | 0.225 | 0.750 | 0.500 | 0.750 | 0.500 |
| qwen235b | musique | random_relay | board | 2 | 1.000 | 1.000 | 0.000 | 0.000 | 1.000 | 1.000 | 0.500 | 0.500 |
| qwen235b | musique | random_relay | extraction | 2 | 1.000 | 1.000 | 0.000 | 0.000 | 1.000 | 1.000 | 0.500 | 0.500 |
| qwen235b | musique | redundancy_aware_relay | board | 2 | 1.000 | 1.000 | 0.000 | 0.000 | 1.000 | 1.000 | 0.500 | 0.500 |
| qwen235b | musique | redundancy_aware_relay | extraction | 2 | 1.000 | 1.000 | 0.000 | 0.000 | 1.000 | 1.000 | 0.500 | 0.500 |
| qwen235b | musique | score_ranked_relay | board | 2 | 1.000 | 1.000 | 0.000 | 0.000 | 1.000 | 1.000 | 0.500 | 0.500 |
| qwen235b | musique | score_ranked_relay | extraction | 2 | 1.000 | 1.000 | 0.000 | 0.000 | 1.000 | 1.000 | 0.500 | 0.500 |
| qwen235b | musique | summary_exchange | board | 2 | 1.000 | 1.000 | 0.000 | 0.000 | 1.000 | 1.000 | 0.500 | 0.500 |
| qwen235b | silobench | random_relay | board | 4 | 0.750 | 1.000 | 0.250 | 0.000 | 0.750 | 1.000 | 0.500 | 0.750 |
| qwen235b | silobench | random_relay | extraction | 4 | 0.750 | 1.000 | 0.250 | 0.000 | 0.750 | 1.000 | 0.500 | 0.750 |
| qwen235b | silobench | redundancy_aware_relay | board | 4 | 0.750 | 1.000 | 0.250 | 0.000 | 0.750 | 1.000 | 0.500 | 0.750 |
| qwen235b | silobench | redundancy_aware_relay | extraction | 4 | 0.750 | 1.000 | 0.250 | 0.000 | 0.750 | 1.000 | 0.500 | 0.750 |
| qwen235b | silobench | score_ranked_relay | board | 4 | 0.750 | 1.000 | 0.250 | 0.000 | 0.750 | 1.000 | 0.500 | 0.750 |
| qwen235b | silobench | score_ranked_relay | extraction | 4 | 0.750 | 1.000 | 0.250 | 0.000 | 0.750 | 1.000 | 0.500 | 0.750 |
| qwen235b | silobench | summary_exchange | board | 4 | 0.750 | 0.625 | 0.250 | 0.375 | 0.750 | 0.500 | 0.750 | 0.500 |
| qwen36f | musique | random_relay | board | 2 | 1.000 | 1.000 | 0.000 | 0.000 | 1.000 | 1.000 | 0.500 | 0.500 |
| qwen36f | musique | random_relay | extraction | 2 | 1.000 | 1.000 | 0.000 | 0.000 | 1.000 | 1.000 | 0.500 | 0.500 |
| qwen36f | musique | redundancy_aware_relay | board | 2 | 1.000 | 1.000 | 0.000 | 0.000 | 1.000 | 1.000 | 0.500 | 0.500 |
| qwen36f | musique | redundancy_aware_relay | extraction | 2 | 1.000 | 1.000 | 0.000 | 0.000 | 1.000 | 1.000 | 0.500 | 0.500 |
| qwen36f | musique | score_ranked_relay | board | 2 | 1.000 | 1.000 | 0.000 | 0.000 | 1.000 | 1.000 | 0.500 | 0.500 |
| qwen36f | musique | score_ranked_relay | extraction | 2 | 1.000 | 1.000 | 0.000 | 0.000 | 1.000 | 1.000 | 0.500 | 0.500 |
| qwen36f | musique | summary_exchange | board | 2 | 1.000 | 1.000 | 0.000 | 0.000 | 1.000 | 1.000 | 0.500 | 0.500 |
| qwen36f | silobench | random_relay | board | 4 | 0.750 | 1.000 | 0.250 | 0.000 | 0.750 | 1.000 | 0.000 | 0.250 |
| qwen36f | silobench | random_relay | extraction | 4 | 0.750 | 1.000 | 0.250 | 0.000 | 0.750 | 1.000 | 0.000 | 0.250 |
| qwen36f | silobench | redundancy_aware_relay | board | 4 | 0.750 | 1.000 | 0.250 | 0.000 | 0.750 | 1.000 | 0.000 | 0.250 |
| qwen36f | silobench | redundancy_aware_relay | extraction | 4 | 0.750 | 1.000 | 0.250 | 0.000 | 0.750 | 1.000 | 0.000 | 0.250 |
| qwen36f | silobench | score_ranked_relay | board | 4 | 0.750 | 1.000 | 0.250 | 0.000 | 0.750 | 1.000 | 0.250 | 0.500 |
| qwen36f | silobench | score_ranked_relay | extraction | 4 | 0.750 | 1.000 | 0.250 | 0.000 | 0.750 | 1.000 | 0.250 | 0.500 |
| qwen36f | silobench | summary_exchange | board | 4 | 0.750 | 1.000 | 0.250 | 0.000 | 0.750 | 1.000 | 0.500 | 0.750 |

## Full-run estimate

Scored pilot cases: 126; logged calls: 190 (64 were retried after a 2000-token truncation; max_tokens raised to 4096 for the scored run). Full run: 3 models x (52 Silo-Bench + 100 MuSiQue) traces x (3 relay protocols x 2 checkpoints + summary exchange x 1 board checkpoint) = 3,192 calls. At the pilot cost per call ($0.000911 over all logged calls), estimated full cost **$2.91**; the estimate may rise with 4096-token outputs, so the proposed cap is **$5.00 per stage**. No full run starts without approval.

