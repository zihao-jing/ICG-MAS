# Redundancy and useful budget under the paper definitions

2026-11-15. $0, no model calls. RedundancyRate = mean pairwise Jaccard similarity of transmitted units; UsefulBudget = distinct best-matched gold support texts / transmitted units. k = 3.

| protocol | n | RedundancyRate | UsefulBudget |
| --- | ---: | ---: | ---: |
| random_relay | 300 | 0.133 | 0.042 |
| redundancy_aware_relay | 300 | 0.133 | 0.042 |
| score_ranked_relay | 300 | 0.133 | 0.042 |

## By model

| model | protocol | n | RedundancyRate | UsefulBudget |
| --- | --- | ---: | ---: | ---: |
| gemma31b | random_relay | 100 | 0.131 | 0.038 |
| gemma31b | redundancy_aware_relay | 100 | 0.131 | 0.038 |
| gemma31b | score_ranked_relay | 100 | 0.131 | 0.038 |
| gpt4omini | random_relay | 100 | 0.108 | 0.047 |
| gpt4omini | redundancy_aware_relay | 100 | 0.108 | 0.047 |
| gpt4omini | score_ranked_relay | 100 | 0.108 | 0.047 |
| qwen235b | random_relay | 100 | 0.159 | 0.041 |
| qwen235b | redundancy_aware_relay | 100 | 0.159 | 0.041 |
| qwen235b | score_ranked_relay | 100 | 0.159 | 0.041 |
