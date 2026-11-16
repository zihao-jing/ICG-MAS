# LLM labeller pilot: run record

2026-11-12. Model `anthropic/claude-haiku-5.5` through the OpenRouter key in
`.env`. Twenty traces (12 E1 anchor runs, 8 Silo-Bench anchor files) drawn with
seed 42 from the 150-trace validation set, two author labels each
(`pilot_20.jsonl`). Every call is logged in the pilot directory; no call was
made with another provider. Cap: **$0.25**.

## 1. Attempts and spend

Each attempt used the same 20 traces. The raw call logs are
`calls_attempt1.jsonl`, `calls_attempt2.jsonl`, and `calls.jsonl` (attempt 3,
the scored run). Costs are recomputed from the `cost_usd` field in each
record; usage prices are $0.10/MTok input and $0.50/MTok output.

| attempt | change | parsed | cost |
| --- | --- | ---: | ---: |
| 1 | first run, reasoning on, 400 max tokens | 0/20 | $0.017085 |
| 2 | `openrouter_reasoning = false`, 600 max tokens | 18/20 | $0.015904 |
| 3 | added "do not solve or recompute", 800 max tokens | 20/20 | $0.015750 |
| **total** | | | **$0.048739** |

Attempt 1 produced no parseable verdict: 18 records were empty and 2 were
truncated by the reasoning budget. In attempt 2 the two Silo-Bench counting
tasks spent the 600-token budget without a verdict. Attempt 3 added the
instruction not to solve the task and raised the budget to 800; all 20 parsed.
Sum check: 0.017085 + 0.015904 + 0.015750 = 0.048739.

## 2. Per-trace labels against the authors

`E1` token-F1 is exact match on the project `normalize()` (lowercase, articles
removed, punctuation mapped to a space); 1.0 means the answer is exactly right
under the scorer.

| # | trace | task | labeller | author A | author B | token-F1 | check |
| ---: | --- | --- | --- | --- | --- | ---: | --- |
| 1 | Anchor Q03 run 3 | E1 | CORRECT | DEFECT | DEFECT | 0.833 | disagree |
| 2 | Anchor Q22 run 1 | E1 | DEFECT | DEFECT | DEFECT | 0.000 | agree |
| 3 | Anchor Q14 run 1 | E1 | CORRECT | CORRECT | CORRECT | 1.000 | agree |
| 4 | Anchor Q20 run 3 | E1 | DEFECT | DEFECT | DEFECT | 0.000 | agree |
| 5 | Anchor Q05 run 3 | E1 | DEFECT | DEFECT | DEFECT | 0.000 | agree |
| 6 | Anchor Q16 run 1 | E1 | CORRECT | CORRECT | CORRECT | 0.667 | agree (scorer strict) |
| 7 | Anchor Q14 run 2 | E1 | DEFECT | DEFECT | DEFECT | 0.000 | agree |
| 8 | Anchor Q11 run 2 | E1 | DEFECT | DEFECT | DEFECT | 0.000 | agree |
| 9 | Anchor Q09 run 3 | E1 | CORRECT | DEFECT | DEFECT | 0.010 | disagree |
| 10 | Anchor Q21 run 1 | E1 | DEFECT | DEFECT | DEFECT | 0.000 | agree |
| 11 | Anchor Q02 run 3 | E1 | DEFECT | DEFECT | DEFECT | 0.000 | agree |
| 12 | Anchor Q27 run 2 | E1 | CORRECT | DEFECT | DEFECT | 0.133 | disagree |
| 13 | III-29_n5 | SB | DEFECT | DEFECT | DEFECT | n/a | agree |
| 14 | II-15_n5 | SB | DEFECT | DEFECT | DEFECT | n/a | agree |
| 15 | II-18_n10 (file 06a08e80) | SB | DEFECT | DEFECT | DEFECT | n/a | agree |
| 16 | II-18_n10 (file 1a8765f3) | SB | DEFECT | DEFECT | DEFECT | n/a | agree |
| 17 | III-30_n10 (file 4811fcff) | SB | DEFECT | DEFECT | DEFECT | n/a | agree |
| 18 | III-30_n10 (file 4dfc2cf9) | SB | DEFECT | DEFECT | DEFECT | n/a | agree |
| 19 | III-26_n5 | SB | CORRECT | CORRECT | CORRECT | n/a | agree |
| 20 | I-03_n10 | SB | CORRECT | CORRECT | CORRECT | n/a | agree |

All 20 traces were opened and read against the rendered question, gold,
sources, extraction pool, board, and final answer. Three traces disagree; on
all three the labeller says CORRECT and both authors say DEFECT. The table's
"check" column records the result of that reading, not only the F1.

## 3. The three disagreements, checked against the trace text

- **Q03 run 3.** Gold `[[8, 13, 3.1546], [7, 13, 2.649], [8, 3, 2.4409]]`;
  answer `[(8, 13, 3.156), (7, 13, 2.649), (8, 3, 2.441)]`. Labeller rationale:
  "matches the gold answer ... after rounding to three decimals." The authors
  mark the trace `reached_but_unused`: the correct vectors are on the board,
  but the answer is not the exact computed output. Both authors are right
  under the label guide; the labeller is too lenient on numeric rounding.
- **Q09 run 3.** Gold `{'variance': 0.24, 'max_load': 249, 'min_load': 248}`;
  the answer ends with `max_load = 249` and `min_load = 248` and never states
  the variance (checked: the 5,672-character answer does not contain the word
  "variance"). Labeller rationale: "The variance is not stated in the final
  answer, but the gold variance of 0.24 is not contradicted by it." Authors:
  `reached_but_unused` and `exclude_partial`, both DEFECT. The missing output
  field is a real defect; the labeller invents an absence-of-evidence rule the
  guide does not have.
- **Q27 run 2.** Gold `Ramstein-Miesenbach`; answer "The headquarters of the
  1st Combat Communications Squadron is located at Ramstein Air Base,
  Germany." Labeller rationale: "Ramstein Air Base is the base adjacent to the
  municipality ... so the final answer is a paraphrase that identifies the same
  location." Authors: `reached_but_unused`, both DEFECT. The gold is the
  municipality, not the base.

The three errors share one failure: the labeller accepts a rounded, partial, or
adjacent answer as CORRECT when the author guide requires the gold output.

**Q16 run 1** also has token-F1 below 1.0 (0.667: gold "Rio Linda", answer "Rio
Linda, Sacramento, CA"), but both authors call it CORRECT and the labeller
agrees. That is a scorer-strictness case, not a labeller error. The other 16
traces are exact matches (F1 1.0), clear wrong answers (F1 0.0), or Silo-Bench
structured outputs where token-F1 is not defined and the label rests on the
traces' own scoring.

## 4. Agreement

- Raw agreement: **0.850** (17 of 20 traces; 34 of 40 author comparisons).
- Cohen's κ: **0.634** (34 pairs, 6 defects called correct or vice versa).
- 95% CI: agreement **0.650-1.000**, κ **0.211-1.000**. Cluster bootstrap over
  the 17 trace clusters, 2,000 draws, seed 42.

The point estimates were recomputed from `calls.jsonl` and the author labels in
`pilot_20.jsonl`; they match the numbers reported by the pilot script. The
cluster unit is the anchor question for E1 and the Silo-Bench file name for SB,
so the two repeat files of `II-18_n10` and `III-30_n10` share a cluster.

## 5. Go / no-go

The plan required a lower CI bound of at least 0.80 agreement and κ at least
0.60. The pilot gives 0.650 and 0.211. **Failed.** The label set is not used and
the 150-trace run is not started.

The prompt revision is approved separately: (i) compare the final answer to the
gold exactly after the project `normalize()`, with rounding and extra fields
treated as DEFECT; (ii) require every field of a structured gold answer; (iii)
add generic DEFECT examples that do not come from the 150-trace set. The
revised prompt is frozen as a versioned file with a recorded hash and must be
re-piloted on 20 traces disjoint from both this pilot and the 150, under a new
$0.25 cap, before any full run.