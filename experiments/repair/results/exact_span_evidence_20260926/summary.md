# Exact evidence restoration: six reviewed cases

The evaluation includes only the six source-reviewed evidence-gap cases; the other 14 audit candidates were reclassified as aggregation gaps and excluded. The restored board appends 45 verbatim source spans and 11 source-verified correction notes.

**Result:** 1 of 6 restored answers is correct (16.7%); all six saved original answers were incorrect. The mean paired score change is +0.167. This small selected subset supports only a case-level observation, not a general restoration effect.

| Baseline setting | Case | Original answer | Restored answer | Gold answer | Original score | Restored score |
| --- | --- | --- | --- | --- | ---: | ---: |
| gemma31b_silobench_n10 | III-25_n10 | Insufficient information. | Insufficient information. | [[25.98, 14.89], [27.42, 67.78], [79.6… | 0 | 0 |
| qwen235b_silobench_n5 | I-02_n5 | 29 | 28 | 28 | 0 | 1 |
| qwen235b_silobench_n10 | I-02_n10 | 78 | 73 | 80 | 0 | 0 |
| qwen235b_silobench_n10 | I-07_n10 | 62.14 | 56.76 | 51.62 | 0 | 0 |
| qwen235b_silobench_n10 | I-10_n10 | Insufficient information. | Insufficient information. | 29.04 | 0 | 0 |
| qwen235b_silobench_n10 | III-25_n10 | Insufficient information. | [(55.74603035907123, 42.25572053681904… | [[25.98, 14.89], [27.42, 67.78], [79.6… | 0 | 0 |

All 12 retry calls succeeded: six restored-board calls and six diagnostic exact replays. The exact replays scored 0/6; they are not the paper-facing comparator. The earlier sandbox attempts failed with connection errors and produced no experimental scores.

Machine-readable case outcomes are in `per_case_results.csv` and `combined_results.json`; each setting’s `*_retry1/per_instance_results.jsonl` and response log retain call-level records.
