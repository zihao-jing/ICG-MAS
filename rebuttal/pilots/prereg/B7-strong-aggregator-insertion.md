# B7: direct insertion re-answered by a stronger aggregator

2026-11-15. Frozen before any call. Cap **$3.00**, chunks of $1 or less, every call logged.

## Question

The direct-insertion upper bound is 32 of 59 (oracle fact supplied to the board, trace's own model;
`20261112_missing_fact_repair/direct_insertion/`). Is that ceiling set by the board content or by the
answering model? This rerun keeps the boards and the inserted fact identical and changes only the
aggregator, to Opus 5.5, in both arms.

## Population and inputs (unchanged)

The 59 cases and their exact `control_board` / `insert_board` in
`20261112_missing_fact_repair/direct_insertion/cases.json` (sha checked against that run's
`prompt_manifest.json` before any call). The inserted unit is the missing fact verbatim, appended to the
target agent with unit id `R-ins:0`. No extractor and no delivery gate: the insert arm is still an oracle
upper bound, not an achievable repair.

## Arms and calls

- **control**: original board, Opus 5.5, 59 calls.
- **insert**: original board plus the fact, Opus 5.5, 59 calls.
- System prompt frozen `_AGGREGATION_SYSTEM`, `max_tokens=1024`, temperature 0, one attempt per call,
  failures logged and not retried.

## Comparison

Per case, paired against the earlier run's arms (trace's own model) read from
`20261112_missing_fact_repair/direct_insertion/answers.jsonl`:

- new insert minus earlier insert (the headline);
- new control minus earlier control (aggregator-only drift, no fact);
- new insert minus new control (within-run insertion effect).

Scoring is the frozen exact rule (`answer_f1 == 1.0` with answer aliases). Counts with Clopper-Pearson 95%
intervals; paired differences with an instance-cluster bootstrap (2,000 draws, seed 43). Split by presence
label (`present`, `partial`, `absent`), which is carried from the earlier run.

## Budget

118 Opus 5.5 calls at $4/$20 per million tokens; the board prompts are under 2k tokens, so about $0.9.
Hard cap $3.00 with call-level enforcement, chunks of $1 or less.