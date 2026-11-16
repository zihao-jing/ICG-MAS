# Redundancy tests on existing MuSiQue traces

2026-11-15. $0, no model calls. Units reconstructed from the stored extraction and scoring phases; k = 3 per agent; critical-fact coverage = gold answer string found in a transmitted unit at lexical recall >= 0.8.

| protocol | n | mean redundancy | critical-fact coverage |
| --- | ---: | ---: | ---: |
| random_relay | 300 | 0.002 | 0.763 |
| redundancy_aware_relay | 300 | 0.002 | 0.763 |
| score_ranked_relay | 300 | 0.002 | 0.763 |

## Coverage by redundancy quartile (redundancy-aware and score-ranked pooled)

| quartile | n | mean redundancy | critical-fact coverage |
| --- | ---: | ---: | ---: |
| 1 | 150 | 0.000 | 0.827 |
| 2 | 150 | 0.000 | 0.853 |
| 3 | 150 | 0.000 | 0.693 |
| 4 | 150 | 0.009 | 0.680 |
