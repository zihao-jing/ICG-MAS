# Redundancy rerun with the paper's LLM relevance scorer

2026-11-15. Rule `Redundancy-LLM-scorer.md` (sha `59e04374...`). Qwen-235B with the paper's scoring prompt; rebuilt units, k = 3, rho = .5. Spend $0.016782, cap $0.20.

| protocol | n | Red [95% CI] | UB [95% CI] |
| --- | ---: | --- | --- |
| random_relay | 30 | 0.169 [0.142, 0.196] | 0.056 [0.028, 0.089] |
| score_ranked_relay | 30 | 0.205 [0.176, 0.232] | 0.050 [0.022, 0.083] |
| redundancy_aware_relay | 30 | 0.182 [0.155, 0.209] | 0.044 [0.017, 0.078] |

Crowding-out: useful budget by Red quartile [0.0333, 0.0444, 0.0444, 0.0667].
Red intervals overlap across all protocols: True.
