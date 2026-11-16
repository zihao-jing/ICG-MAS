# Silo-Bench two-step proxy pilot

2026-11-15. Rule `Silo-Bench-two-step-pilot.md` (sha `5783d836...`), prompt `proxy_facts_prompt_v3_two_step.json` (sha `7210ce14...`). 20 of 208 traces, seed 50; selection then facts for the selected rows only. Spend $0.226981, cap $1.50.

| quantity | value [95% CI] | bar |
| --- | --- | --- |
| truncated traces | 0/20 (0.0%) [0.0%, 16.8%] | <= 2% |
| facts per trace, mean / max | 7.7 / 10 | mean <= 1.2 x gold, max <= 30 |
| gold supports per trace, mean | 8.0 | — |
| facts / gold | 0.96 | <= 1.20 |
| fact equivalence to gold | 98.7% [95.4%, 99.8%] (n=153) | reported, not a bar |

**Pilot PASSES.** Truncation bar pass; granularity bar pass.

| trace | selected rows | facts | gold supports | truncated | agreement |
| --- | ---: | ---: | ---: | --- | --- |
| qwen235b|SB|results/run_qwen235b_n10|redundancy_aware_relay|II-16_n10 | 10 | 10 | 10 | no | True |
| qwen235b|SB|results/run_qwen235b_n10|redundancy_aware_relay|III-27_n10 | 10 | 10 | 10 | no | True |
| qwen235b|SB|results/run_qwen235b_n10|score_ranked_relay|II-12_n10 | 10 | 10 | 10 | no | True |
| qwen235b|SB|results/run_qwen235b_n10|score_ranked_relay|II-19_n10 | 10 | 10 | 10 | no | True |
| qwen235b|SB|results/run_qwen235b_n10|summary_exchange|I-04_n10 | 1 | 1 | 10 | no | True |
| qwen235b|SB|results/run_qwen235b_n10|random_relay|III-26_n10 | 10 | 10 | 10 | no | True |
| qwen235b|SB|results/run_qwen235b_n10|random_relay|III-30_n10 | 10 | 10 | 10 | no | True |
| qwen235b|SB|results/run_qwen235b_n10|score_ranked_relay|I-05_n10 | 10 | 10 | 10 | no | True |
| qwen235b|SB|results/run_qwen235b_n10|score_ranked_relay|I-06_n10 | 10 | 10 | 10 | no | True |
| qwen235b|SB|results/run_qwen235b_n10|summary_exchange|I-07_n10 | 10 | 10 | 10 | no | True |
| qwen235b|SB|results/run_qwen235b_n10|summary_exchange|II-12_n10 | 10 | 10 | 10 | no | True |
| qwen235b|SB|results/run_qwen235b_n10|summary_exchange|II-18_n10 | 10 | 10 | 10 | no | True |
| qwen235b|SB|results/run_qwen235b_n5|random_relay|III-22_n5 | 5 | 6 | 5 | no | True |
| qwen235b|SB|results/run_qwen235b_n5|random_relay|III-28_n5 | 5 | 5 | 5 | no | True |
| qwen235b|SB|results/run_qwen235b_n5|redundancy_aware_relay|I-08_n5 | 5 | 5 | 5 | no | True |
| qwen235b|SB|results/run_qwen235b_n5|redundancy_aware_relay|II-15_n5 | 5 | 5 | 5 | no | True |
| qwen235b|SB|results/run_qwen235b_n5|score_ranked_relay|I-08_n5 | 5 | 5 | 5 | no | True |
| qwen235b|SB|results/run_qwen235b_n5|score_ranked_relay|III-22_n5 | 5 | 6 | 5 | no | True |
| qwen235b|SB|results/run_qwen235b_n5|score_ranked_relay|III-26_n5 | 5 | 5 | 5 | no | True |
| qwen235b|SB|results/run_qwen235b_n5|summary_exchange|II-17_n5 | 5 | 5 | 5 | no | True |

## Ledger
Spend $0.226981.
