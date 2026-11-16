# Exploratory whole-source augmentation results

These historical source arms appended entire benchmark supports or input shards. They are not exact missing-span repair and must not be used as evidence that a specific omitted fact caused failure.

Combined 456 unique instances from 19 run directories.
Scores are exact match for Silo-Bench and answer F1 for MuSiQue. Differences compare each intervention with the cached original answer on the same cases.

## Crossover comparisons

| Setting | Diagnosis | N | Original | Gemini score (gain) | Whole-source score (gain) | Gemini − whole source [95% CI] |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| gemma31b_musique | aggregation_gap | 74 | 0.124 | 0.184 (+0.059) | 0.325 (+0.201) | -0.141 [-0.249, -0.035] |
| gemma31b_silobench_n10 | aggregation_gap | 13 | 0.000 | 0.000 (+0.000) | 0.000 (+0.000) | +0.000 [+0.000, +0.000] |
| gemma31b_silobench_n10 | evidence_gap | 5 | 0.000 | 0.200 (+0.200) | 0.200 (+0.200) | +0.000 [+0.000, +0.000] |
| gemma31b_silobench_n5 | aggregation_gap | 15 | 0.000 | 0.200 (+0.200) | 0.333 (+0.333) | -0.133 [-0.400, +0.133] |
| gpt4omini_musique | aggregation_gap | 71 | 0.134 | 0.324 (+0.190) | 0.140 (+0.006) | +0.183 [+0.092, +0.276] |
| gpt4omini_silobench_n10 | aggregation_gap | 17 | 0.000 | 0.176 (+0.176) | 0.000 (+0.000) | +0.176 [+0.000, +0.412] |
| gpt4omini_silobench_n10 | evidence_gap | 5 | 0.000 | 0.000 (+0.000) | 0.000 (+0.000) | +0.000 [+0.000, +0.000] |
| gpt4omini_silobench_n5 | aggregation_gap | 20 | 0.000 | 0.400 (+0.400) | 0.000 (+0.000) | +0.400 [+0.200, +0.600] |
| gpt4omini_silobench_n5 | evidence_gap | 2 | 0.000 | 0.500 (+0.500) | 0.500 (+0.500) | +0.000 [+0.000, +0.000] |
| qwen235b_musique | aggregation_gap | 68 | 0.216 | 0.347 (+0.131) | 0.276 (+0.059) | +0.072 [-0.020, +0.161] |
| qwen235b_n10 | aggregation_gap | 16 | 0.000 | 0.062 (+0.062) | 0.000 (+0.000) | +0.062 [+0.000, +0.188] |
| qwen235b_n10 | evidence_gap | 6 | 0.000 | 0.167 (+0.167) | 0.000 (+0.000) | +0.167 [+0.000, +0.500] |
| qwen235b_n5 | aggregation_gap | 18 | 0.000 | 0.389 (+0.389) | 0.056 (+0.056) | +0.333 [+0.111, +0.556] |
| qwen235b_n5 | evidence_gap | 2 | 0.000 | 0.000 (+0.000) | 0.000 (+0.000) | +0.000 [+0.000, +0.000] |

## API outcomes

| Setting | Diagnosis | Arm | Attempted | Successful | Failed | Total model tokens |
| --- | --- | --- | ---: | ---: | ---: | ---: |
| gemma31b_musique | aggregation_gap | exact_replay | 74 | 74 | 0 | 29441 |
| gemma31b_musique | aggregation_gap | gold_support_repair | 74 | 74 | 0 | 55623 |
| gemma31b_musique | aggregation_gap | stronger_model | 74 | 74 | 0 | 94365 |
| gemma31b_musique | baseline_correct | exact_replay | 26 | 26 | 0 | 10275 |
| gemma31b_silobench_n10 | aggregation_gap | exact_replay | 13 | 13 | 0 | 47863 |
| gemma31b_silobench_n10 | aggregation_gap | source_shard_repair | 13 | 13 | 0 | 83869 |
| gemma31b_silobench_n10 | aggregation_gap | stronger_model | 13 | 13 | 0 | 82249 |
| gemma31b_silobench_n10 | baseline_correct | exact_replay | 8 | 8 | 0 | 22951 |
| gemma31b_silobench_n10 | evidence_gap | exact_replay | 5 | 5 | 0 | 28830 |
| gemma31b_silobench_n10 | evidence_gap | source_shard_repair | 5 | 5 | 0 | 51548 |
| gemma31b_silobench_n10 | evidence_gap | stronger_model | 5 | 5 | 0 | 41678 |
| gemma31b_silobench_n5 | aggregation_gap | exact_replay | 15 | 15 | 0 | 52445 |
| gemma31b_silobench_n5 | aggregation_gap | source_shard_repair | 15 | 15 | 0 | 64861 |
| gemma31b_silobench_n5 | aggregation_gap | stronger_model | 15 | 15 | 0 | 88814 |
| gemma31b_silobench_n5 | baseline_correct | exact_replay | 11 | 11 | 0 | 20473 |
| gpt4omini_musique | aggregation_gap | exact_replay | 71 | 71 | 0 | 30121 |
| gpt4omini_musique | aggregation_gap | gold_support_repair | 71 | 71 | 0 | 54645 |
| gpt4omini_musique | aggregation_gap | stronger_model | 71 | 71 | 0 | 106927 |
| gpt4omini_musique | baseline_correct | exact_replay | 29 | 29 | 0 | 11409 |
| gpt4omini_silobench_n10 | aggregation_gap | exact_replay | 17 | 17 | 0 | 34128 |
| gpt4omini_silobench_n10 | aggregation_gap | source_shard_repair | 17 | 17 | 0 | 55414 |
| gpt4omini_silobench_n10 | aggregation_gap | stronger_model | 17 | 17 | 0 | 105360 |
| gpt4omini_silobench_n10 | baseline_correct | exact_replay | 4 | 4 | 0 | 6689 |
| gpt4omini_silobench_n10 | evidence_gap | exact_replay | 5 | 5 | 0 | 14516 |
| gpt4omini_silobench_n10 | evidence_gap | source_shard_repair | 5 | 5 | 0 | 25381 |
| gpt4omini_silobench_n10 | evidence_gap | stronger_model | 5 | 5 | 0 | 45225 |
| gpt4omini_silobench_n5 | aggregation_gap | exact_replay | 20 | 20 | 0 | 27655 |
| gpt4omini_silobench_n5 | aggregation_gap | source_shard_repair | 20 | 20 | 0 | 41112 |
| gpt4omini_silobench_n5 | aggregation_gap | stronger_model | 20 | 20 | 0 | 110516 |
| gpt4omini_silobench_n5 | baseline_correct | exact_replay | 4 | 4 | 0 | 4057 |
| gpt4omini_silobench_n5 | evidence_gap | exact_replay | 2 | 2 | 0 | 1495 |
| gpt4omini_silobench_n5 | evidence_gap | source_shard_repair | 2 | 2 | 0 | 1627 |
| gpt4omini_silobench_n5 | evidence_gap | stronger_model | 2 | 2 | 0 | 8039 |
| qwen235b_musique | aggregation_gap | exact_replay | 68 | 68 | 0 | 34235 |
| qwen235b_musique | aggregation_gap | gold_support_repair | 68 | 68 | 0 | 56563 |
| qwen235b_musique | aggregation_gap | stronger_model | 68 | 68 | 0 | 112728 |
| qwen235b_musique | baseline_correct | exact_replay | 32 | 32 | 0 | 13842 |
| qwen235b_n10 | aggregation_gap | exact_replay | 16 | 16 | 0 | 40719 |
| qwen235b_n10 | aggregation_gap | source_shard_repair | 16 | 16 | 0 | 69128 |
| qwen235b_n10 | aggregation_gap | stronger_model | 16 | 16 | 0 | 93293 |
| qwen235b_n10 | baseline_correct | exact_replay | 4 | 4 | 0 | 7429 |
| qwen235b_n10 | evidence_gap | exact_replay | 6 | 6 | 0 | 16210 |
| qwen235b_n10 | evidence_gap | source_shard_repair | 6 | 6 | 0 | 35326 |
| qwen235b_n10 | evidence_gap | stronger_model | 6 | 6 | 0 | 28251 |
| qwen235b_n5 | aggregation_gap | exact_replay | 18 | 18 | 0 | 31041 |
| qwen235b_n5 | aggregation_gap | source_shard_repair | 18 | 18 | 0 | 56340 |
| qwen235b_n5 | aggregation_gap | stronger_model | 18 | 18 | 0 | 87940 |
| qwen235b_n5 | baseline_correct | exact_replay | 6 | 6 | 0 | 6965 |
| qwen235b_n5 | evidence_gap | exact_replay | 2 | 2 | 0 | 1754 |
| qwen235b_n5 | evidence_gap | source_shard_repair | 2 | 2 | 0 | 2403 |
| qwen235b_n5 | evidence_gap | stronger_model | 2 | 2 | 0 | 7121 |

## Interpretation notes

- Case classes were accepted through a single user confirmation and remain tied to the cached lexical audit hints; the decision sheets do not contain independent per-case semantic annotations.
- Silo-Bench source-shard repair appends all original task shards. It is a source-restoration test, not an atomic-fact repair. MuSiQue has no lexical evidence-gap cases in this run.
- Gemini changes only the aggregation model. The historical whole-source arm appended every gold supporting paragraph on MuSiQue or every original input shard on Silo-Bench while keeping the original model. The original aggregation prompt and generation settings remained fixed.
- The current runner requires exact, explicitly annotated missing source spans for a new evidence-repair run; none of the historical whole-source responses satisfy that definition.
- Repair cases were selected from original failures. Silo-Bench exact match is binary, so their original-run scores are zero by construction; MuSiQue token F1 can give partial credit to an incorrect answer.
- These original-run comparisons show recovery on selected failures. Because selection used the original outcome and decoding is stochastic, the difference can include run-to-run variation; exact replay remains in the per-case results and combined JSON as a diagnostic.
- Failed API arms are omitted from paired comparisons and shown in the API outcomes table.
- The CSV files retain separate 95% bootstrap intervals for each gain versus the original run. The table shows the paired Gemini-versus-source interval to make the intervention comparison visible.
