# Full MuSiQue presence run (rule frozen before any call)

Written 2026-11-13, before the build or any call. This is step 2a of the
reviewer's plan: the full MuSiQue presence run under the frozen pilot rule.
Silo-Bench is excluded because its presence label is not validated; the
fidelity/Dist column is not redone and stays marked unvalidated.

## Scope and stage

- Stage: relay checkpoints (extraction pool and shared board).
- Models: Qwen-235B, Mistral-S, Qwen-3.6-Flash.
- Benchmark: MuSiQue, all 100 instances per model.
- Protocols: summary exchange (board checkpoint only, as the trace package
  has no separate extraction checkpoint for it), random relay, score-ranked
  relay, redundancy-aware relay (both checkpoints).
- Runs: `results/run_qwen235b_musique`, `results/run_musique_mistrals`,
  `results/run_musique_100`.

## Facts and labels

The fact list is the audit's gold critical units (`source_supports`, the
MuSiQue supporting paragraphs), the same units the old lexical rule scores.
Old columns are the frozen lexical rule recomputed on the same traces
(`align_gold_to_transmitted`: any number/token overlap). New columns are the
V9 per-fact presence label (Claude Haiku 5.5, `per_fact_prompt_v9.json`),
validated on MuSiQue at extraction (0.968, kappa 0.857) and at the board
(carrier 0.952, kappa 0.796) in V9. Presence means the fact's central claim is
carried; a sub-claim check follows in step 2b before any MuSiQue number enters
the table.

## Columns

- critical recall (CR) = facts carried / facts; carried = status present or
  partial. Omission = 1 - CR.
- complete coverage = traces with every fact carried / traces.
- aggregation failure (AF) = complete coverage AND a non-perfect answer /
  traces; the answer is held fixed from the saved run.
- fidelity/Dist is not reported.

## Run and cap

2,100 calls (3 models x 100 instances x [3 relay protocols x 2 checkpoints +
summary exchange x 1 board checkpoint]). Cap **$5.00**; every call logs intent
and result with `cost_usd`. The report gives per-cell old and new columns and
pooled 95% CIs from an instance-cluster bootstrap (seed 43, 2,000 draws), plus
the spend.