# Opus 5.5 check of the Gemini answer-equivalence checker, rule v1 (frozen before any call; 2026-11-16)

## Question

Does the Gemini 3.6 Flash checker (frozen prompt `20261112_answer_equiv/answer_equiv_v1.json`, unchanged) agree with Opus 5.5 on a stratified sample of the 150 author-labelled rows, well enough to use as the restore-subset checker?

## Sample

- 40 rows from `20261112_labeller/validation_150.jsonl`, drawn with seed 43 within these strata (author label x Gemini verdict on the same row): CORRECT/EQUIVALENT 12; CORRECT/NOT_EQUIVALENT 2 (all); DEFECT/EQUIVALENT 7 (all); DEFECT/NOT_EQUIVALENT 16; DEFECT/unparsed 3 (all). Unique item_ids only.
- Item list: `20261116_opus_checker_check/items.json`, sha256 500f30a4460fdcb69470b6f1045e6488f79088560e12141d862085a7129e554d.

## Reference and transport

- Opus 5.5 through the claude CLI only: empty temporary directory, tools disabled, the frozen prompt as system prompt, JSON output.
- Cap: $1.00 total. Hard stop before each call. Each call is logged with the CLI-reported cost and the API-equivalent cost; the cap uses the larger of the two. Before a call the estimate is the mean cost of the calls so far.

## Scoring

- Each row is scored on Gemini verdict vs Opus verdict (EQUIVALENT / NOT_EQUIVALENT). An unparsed Opus verdict is recorded and not scored.
- Each stratum is weighted by its population size (unique items in the 150) divided by its sampled rows, so the agreement and kappa describe the 150-row population.
- Interval for kappa: stratified bootstrap, 2,000 draws, seed 43.

## Pass bars (fixed before the run)

- weighted agreement >= 0.90;
- weighted kappa >= 0.75;
- EQUIVALENT recall against Opus (weighted) >= 0.85.

If all three pass, the restore headline is 41/92 vs 5/92 with the Gemini checker and its Opus agreement stated. If any fails, the headline stays 13/92.
