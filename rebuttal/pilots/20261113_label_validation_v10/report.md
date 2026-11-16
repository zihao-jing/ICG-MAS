# V10 fidelity with Claude Opus 5.5 and constructed distortions

Rule `LABEL_RULE_V10.md` (sha256 `55a9b3e0cab9`); reference labels `reference_labels_v10.json` (sha256 `9d9cf5d5919c`), frozen before the Opus calls. Reference **Gemini 3.6 Flash**; labeller **Claude Opus 5.5**, V9 prompt text. 120 natural cases + 37 constructed distorted facts; spend $3.373441, whole-run cap $5.00. Bar 0.80/0.60 (replaces the 0.85 in V7-V9). Stage: relay checkpoints.

## Natural cases

| checkpoint | strict fidelity (faithful vs not) | distorted vs not |
| --- | --- | --- |
| extraction | 159/163 = 0.975 [0.938, 0.993]; kappa 0.787 [0.488, 0.957] **PASS** | 160/163 = 0.982 [0.947, 0.996]; kappa 0.658 [0.000, 1.000] **PASS** |
| board | 158/163 = 0.969 [0.930, 0.990]; kappa 0.721 [0.429, 0.930] **PASS** | 161/163 = 0.988 [0.956, 0.999]; kappa 0.744 [0.000, 1.000] **PASS** |
| pooled | 317/326 = 0.972 [0.948, 0.987]; kappa 0.755 [0.538, 0.899] **PASS** | 321/326 = 0.985 [0.965, 0.995]; kappa 0.699 [0.246, 1.000] **PASS** |

Presence: 366/384 = 0.953.

## Constructed distortions (37 planted facts)

Opus calls the planted fact distorted 31/37; the reference 32/37.

| view | strict fidelity | distorted vs not |
| --- | --- | --- |
| all planted (absent = not faithful) | 35/37 = 0.946 [0.818, 0.993]; kappa 0.641 [0.000, 1.000] **PASS** | 32/37 = 0.865 [0.712, 0.955]; kappa 0.467 [-0.049, 0.841] **FAIL** |
| both carried | 32/34 = 0.941 [0.803, 0.993]; kappa 0.638 [0.000, 1.000] **PASS** | 31/34 = 0.912 [0.763, 0.981]; kappa 0.532 [0.000, 1.000] **FAIL** |

## Verdict

Strict fidelity passes the **0.80/0.60** bar at both natural checkpoints and on the constructed distortions. The board checkpoint is the stage used by the main table. The "distorted vs not" secondary view fails the bar on the constructed set (kappa 0.467 all planted, 0.532 both carried), so **the Dist column is not validated by this run**; only strict fidelity is.

A PASS is cross-model agreement on these cases; the reference is an LLM, not author ground truth. Constructed distortions test detection of a known corruption, not the natural failure distribution.

