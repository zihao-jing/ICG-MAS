# Restore-the-source test on real-run distortion diagnoses

Rule `RESTORE_RULE.md` (sha256 `ae29bcafaa11`), frozen before any call. Pilot 40 of 184 unique cases (`sha256('43|restore|'+instance)` order). Spend $0.008642; cap $5.00. Stages: relay checkpoint (the distorted unit) and final aggregation (the two arms).

## Confirmation

Cases whose source sentence was confirmed to state the fact and is verbatim in the source shard: **23/40** (57.5%, 95% CI 40.9-73.0).

| instance | model | source states fact | board contradicts | confirmed |
| --- | --- | --- | --- | --- |
| 4hop1__145494_698949_157828_162309 | gemma31b | no | no | no |
| 4hop1__580153_49925_13759_736921 | gemma31b | no | no | no |
| 2hop__557411_652060 | gemma31b | no | no | no |
| 2hop__757497_78606 | gpt4omini | yes | yes | yes |
| 2hop__124807_135019 | gemma31b | yes | no | yes |
| 2hop__156658_155922 | gemma31b | yes | no | yes |
| 4hop2__71753_648517_70784_61381 | gemma31b | no | yes | no |
| 4hop1__88342_49853_128008_46894 | qwen235b | yes | yes | yes |
| 2hop__632870_22402 | gemma31b | yes | no | yes |
| 2hop__351275_75487 | gemma31b | yes | no | yes |
| 4hop2__161602_426860_88460_126088 | qwen235b | yes | no | yes |
| 3hop2__28476_14777_9331 | gpt4omini | yes | no | yes |
| 2hop__123509_5385 | gemma31b | yes | yes | yes |
| 3hop1__68732_39743_24526 | gemma31b | yes | no | yes |
| 3hop1__145924_131905_41948 | qwen235b | no | no | no |
| 4hop1__344155_378185_282674_759393 | qwen235b | no | no | no |
| 4hop2__161602_426860_88460_21062 | qwen235b | no | no | no |
| 4hop2__9988_261673_70784_79935 | gemma31b | no | no | no |
| 4hop2__71753_729371_70784_79935 | gemma31b | no | no | no |
| 3hop1__831499_228453_10972 | gemma31b | no | no | no |
| 4hop1__370129_621192_10659_42311 | gpt4omini | yes | no | yes |
| 4hop1__636860_49925_13759_736921 | gemma31b | no | no | no |
| 2hop__124932_278133 | gemma31b | yes | no | yes |
| 3hop1__127821_157828_239539 | qwen235b | no | no | no |
| 2hop__839126_472799 | gemma31b | yes | no | yes |
| 4hop1__163763_49925_13759_736921 | gemma31b | no | no | no |
| 4hop1__813171_153080_159767_81096 | qwen235b | yes | no | yes |
| 2hop__810411_159673 | gemma31b | yes | no | yes |
| 2hop__673655_316668 | gemma31b | yes | no | yes |
| 2hop__756620_127399 | gemma31b | yes | no | yes |
| 2hop__107548_124896 | gemma31b | yes | no | yes |
| 2hop__280451_84616 | gemma31b | yes | no | yes |
| 3hop1__529164_567566_84283 | gemma31b | yes | no | yes |
| 3hop1__159737_160713_77246 | qwen235b | no | no | no |
| 3hop1__617062_127905_92225 | gpt4omini | no | no | no |
| 2hop__142198_152093 | gemma31b | yes | no | yes |
| 3hop1__462960_160545_34754 | gpt4omini | no | no | no |
| 3hop1__469478_15840_36002 | gemma31b | yes | no | yes |
| 2hop__86689_728109 | gemma31b | no | no | no |
| 2hop__286_574195 | gemma31b | yes | no | yes |

## Answer arms (confirmed cases)

Control exact **0/23**; restore exact **4/23** (17.4%, 95% CI 5.0-38.8). Mean F1 control 0.000, restore 0.338. Paired: 4 improved, 0 worse, 19 same.

## Reading

Only 23 of 40 pilot cases have a source sentence that the labeller confirms states the fact and is verbatim in the shard. The remainder are distortion diagnoses whose target unit is not a near-copy of a source fact (refusals, headers, unrelated text), so the audit's distortion label is not restorable from the source. On the confirmed cases the restore arm is reported above; the sample is descriptive and small.
