# E4 direct insertion: run report

Read before any contrast. Counts, failures, manipulation checks, volume match and cost only;
no answer or score is read here.

R-ins appends the targeted-fact text as one board unit; it is a **positive control**, and
its manipulation check passes by construction. V-ins appends a donor passage matched to its
token count.

| Case | Model | Setting | R-ins tokens | V-ins tokens | Ratio | Volume match | R-ins manipulation | V-ins manipulation | Donor fallback |
|---|---|---|---:|---:|---:|---|---|---|---|
| 3hop1__132795_40769_64047 | google/gemma-4-31b-it | MQ | 13 | 14 | 1.08 | yes | pass | pass | yes |
| 2hop__280583_229757 | google/gemma-4-31b-it | MQ | 10 | 10 | 1.00 | yes | pass | pass | yes |
| 3hop1__147225_30587_83479 | google/gemma-4-31b-it | MQ | 8 | 8 | 1.00 | yes | pass | pass | yes |
| 4hop1__814349_624859_355213_203322 | google/gemma-4-31b-it | MQ | 11 | 11 | 1.00 | yes | pass | pass | no |
| 3hop2__132957_433432_40768 | google/gemma-4-31b-it | MQ | 16 | 16 | 1.00 | yes | pass | pass | yes |
| 2hop__491195_265959 | google/gemma-4-31b-it | MQ | 13 | 13 | 1.00 | yes | pass | pass | yes |
| 3hop2__304722_590317_63959 | google/gemma-4-31b-it | MQ | 29 | 29 | 1.00 | yes | pass | pass | yes |
| 2hop__142621_225454 | google/gemma-4-31b-it | MQ | 11 | 11 | 1.00 | yes | pass | pass | yes |
| III-29_n5 | google/gemma-4-31b-it | SB-5 | 14 | 14 | 1.00 | yes | pass | pass | yes |
| 3hop1__147225_30587_83479 | openai/gpt-4o-mini | MQ | 14 | 14 | 1.00 | yes | pass | pass | yes |
| 4hop1__814349_624859_355213_203322 | openai/gpt-4o-mini | MQ | 13 | 13 | 1.00 | yes | pass | pass | no |
| 2hop__511454_120259 | openai/gpt-4o-mini | MQ | 20 | 19 | 0.95 | yes | pass | pass | no |
| 2hop__28287_89399 | openai/gpt-4o-mini | MQ | 28 | 28 | 1.00 | yes | pass | pass | yes |
| 3hop1__465684_160545_62931 | qwen/qwen3-235b-a22b-2507 | MQ | 13 | 13 | 1.00 | yes | pass | pass | no |
| 4hop1__802394_153080_33897_81096 | qwen/qwen3-235b-a22b-2507 | MQ | 23 | 23 | 1.00 | yes | pass | pass | yes |
| II-18_n10 | qwen/qwen3-235b-a22b-2507 | SB-10 | 11 | 11 | 1.00 | yes | pass | pass | yes |
| II-18_n5 | qwen/qwen3-235b-a22b-2507 | SB-5 | 13 | 14 | 1.08 | yes | pass | pass | yes |

## Counts

- Cases: **17**; planned calls 34; dispatched **34**; failed **0**.
- R-ins manipulation check: **17 of 17 pass**; V-ins: **17 of 17 pass**.
- Volume matched (equal added-unit count and ±10% added tokens): **17 of 17**.
- Unmatched controls: **0**.
- Donor fallback cases (donor is a support agent): **13 of 17**.
- Cost: **$0.008385** against the $0.10 cap; calls 34 of the 34 cap.
- First/last call (from the ledger): 1794277442.361587 / 1794277617.731462 (epoch seconds).

Failed calls:

- none.

No contrast, answer or score is in this file.
