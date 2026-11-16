# Repair-study result directories

The exploratory three-baseline report is [`three_model_summary/summary.md`](three_model_summary/summary.md). It combines 456 distinct cases and 1,120 successful result rows from 19 directories: the following 10 initial-run directories and 9 crossover directories. Its source arm added whole supports or shards, so it is not evidence for exact missing-span repair.

The completed one-agent Gemini-middle versus Gemini-terminal comparison on all 326 revised aggregation-gap cases is [`aggregation_stage_swap_20260926/summary.md`](aggregation_stage_swap_20260926/summary.md). All 652 new calls succeeded. The exact-span evidence-only run on six cases is [`exact_span_evidence_20260926/summary.md`](exact_span_evidence_20260926/summary.md).

| Baseline | Dataset and setting | Included result directory |
| --- | --- | --- |
| Gemma 4 31B | MuSiQue | `gemma31b_musique_full` |
| Gemma 4 31B | Silo-Bench, 5 agents | `gemma31b_silobench_n5_full` |
| Gemma 4 31B | Silo-Bench, 10 agents | `gemma31b_silobench_n10_network`, `gemma31b_silobench_n10_supplement` |
| GPT-4o-mini | MuSiQue | `gpt4omini_musique_full` |
| GPT-4o-mini | Silo-Bench, 5 agents | `gpt4omini_silobench_n5_full` |
| GPT-4o-mini | Silo-Bench, 10 agents | `gpt4omini_silobench_n10_full` |
| Qwen-235B | MuSiQue | `qwen235b_musique_full` |
| Qwen-235B | Silo-Bench, 5 agents | `qwen235b_silobench_n5_full` |
| Qwen-235B | Silo-Bench, 10 agents | `qwen235b_silobench_n10_full` |

The crossover directories are `gemma31b_musique_cross`, `gemma31b_silobench_n5_cross`, `gemma31b_silobench_n10_cross`, `gpt4omini_musique_cross`, `gpt4omini_silobench_n5_cross`, `gpt4omini_silobench_n10_cross`, `qwen235b_musique_cross`, `qwen235b_silobench_n5_cross`, and `qwen235b_silobench_n10_cross`. They add 332 successful responses: source restoration on 312 aggregation-gap cases and Gemini on 20 evidence-gap cases.

The historical report compares each intervention with the cached original answer on the same selected cases, and gives direct Gemini-versus-whole-source comparisons, API outcomes, and interpretation limits. `crossover_comparisons.csv` holds the full crossover scores and confidence intervals; `paired_comparisons.csv` holds each intervention's gain versus the original run. `combined_results.json` also retains exact-replay diagnostics. `arm_scores.csv` contains per-arm API summaries. The individual included directories retain per-case responses and run metadata. Exact-span review sheets are under `../exact_span_review/`; the completed six-case exact-span run is linked above.

All `mistrals_*` directories contain incomplete attempts caused by repeated upstream rate limits. Mistral was dropped at the user's request and is **not** in the three-baseline report. The `gemma31b_silobench_n10` and `gemma31b_silobench_n10_rerun` setup attempts are also excluded; the two included Gemma ten-agent batches cover that setting without duplicate cases.

The decision sheets in `../all_run_decisions/` record the user's global acceptance of the cached lexical classifications. They do not provide independent per-case semantic annotations. Silo-Bench evidence-gap runs use all original input shards as source restoration because the dataset has no minimal atomic-fact labels; these results should not be described as controlled fact-level repair.
