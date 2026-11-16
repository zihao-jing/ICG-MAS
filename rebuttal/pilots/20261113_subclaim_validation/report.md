# Sub-claim presence rule B validation (fresh MuSiQue board cases)

Rule `VALIDATION_RULE.md` (sha256 `84bbd35007e8`); prompt `subclaim_prompt.json` (sha256 `415acd95d262`), unchanged from the pilot. Reference labels frozen before the Haiku calls (`reference_labels.json`, sha256 `f29cb2c931fe`). Reference Gemini 3.6 Flash; labeller Claude Haiku 5.5. 59 of 59 cases scored (0 reference calls excluded), 144 fact comparisons; spend **$0.889705**, caps $2.00 + $1.00. Stage: MuSiQue shared board.

Presence agreement **139/144 = 0.965** (95% CI 0.921-0.989); kappa **0.881** (0.748-0.978) - **PASS** against 0.80/0.60 on the point estimate; the kappa lower bound 0.748 is above 0.60. Stratum caveat: in the A-complete stratum kappa is ~0 because almost every fact is present under both labels (prevalence), so the overall kappa is carried by the A-not-complete stratum.

| stratum | agreement | kappa |
| --- | --- | --- |
| a_complete | 74/78 = 0.949 [0.874, 0.986] | -0.020 |
| a_not_complete | 65/66 = 0.985 [0.918, 1.000] | 0.967 |

PASS allows the full B run as a stricter column beside central-claim A. B is not a replacement; A stays the validated table label with the central-claim qualifier. Coverage and critical recall remain upper bounds, loss and omission lower bounds. The reference is a stronger AI model, not author ground truth.

