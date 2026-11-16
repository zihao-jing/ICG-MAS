# Silo-Bench presence validation, expansion + combined

Expansion rule `RULE_EXPANSION.md` (sha256 `6020f343c9ae`); reference labels frozen before the expansion Haiku calls (`reference_labels_v2.json`, sha256 `e2930be8dcbb`). 48 fresh cases requested (2 per cell, disjoint from the first 24, anchor and pilot); 2 excluded after two failed reference calls and 1 after a labeller parse failure, giving 45 scored expansion cases. Reference Gemini 3.6 Flash; labeller Claude Haiku 5.5. Spend **$1.048974** across both stages, caps $2.00+$0.50 (first) and $1.50+$0.30 (expansion).

Combined presence agreement **471/515 = 0.915** (95% CI 0.887-0.937); kappa **0.653** (0.447-0.854) - **PASS** against 0.80/0.60 on the point estimate; the kappa **lower bound 0.447** is below 0.60, so the interval remains wide and this is not a precise reliability claim.

| stage | n facts | agreement [95% CI] | kappa [95% CI] |
| --- | ---: | --- | --- |
| first 24 cases | 180 | 163/180 = 0.906 [0.853, 0.944] | 0.702 |
| expansion 45 cases | 335 | 308/335 = 0.919 [0.885, 0.946] | 0.604 (0.416-0.887) |
| combined 69 cases | 515 | 471/515 = 0.915 [0.887, 0.937] | 0.653 (0.447-0.854) |

| n_agents | agreement | kappa |
| --- | --- | --- |
| n=5 | 166/175 = 0.949 [0.905, 0.976] | 0.699 |
| n=10 | 305/340 = 0.897 [0.860, 0.927] | 0.634 |

The first 24-case kappa interval 0.242-0.940 is kept on record; the combined interval is the one to read. This remains a cross-model check against Gemini, not author ground truth. The combined PASS allows the Silo-Bench rows into the table under the central-claim presence qualifier.

