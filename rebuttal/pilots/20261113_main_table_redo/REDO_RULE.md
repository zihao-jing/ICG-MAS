# Main-table redo rule (frozen before any call)

Written 2026-11-13, before the pilot call. Stage: relay checkpoints
(extraction pool and shared board) of the 2,400-trace Stage 2 MuSiQue main
table. Instrument: the per-fact carrier labeller (Claude Haiku 5.5, prompt
v3), whose validation record is
`rebuttal/pilots/20261113_per_fact_labeller/VALIDATION_RECORD.md`.

## Population

`rebuttal/results/batch1/expansion_stage2`: 800 MuSiQue instances at each of
gemma31b, gpt4omini and qwen235b, score-ranked relay = **2,400 traces**. The
fact list is the frozen audit matcher record for the same (model, instance)
(`expansion_stage2/matcher`, `facts.facts`), 7,665 facts in total. Both
checkpoints are taken from the saved trace package: `extraction` and `board`.
The population is written to `population.json` with its sha256 frozen in
`run_manifest.json` before the first call.

## Old and new columns

Both instruments see the same facts at the same checkpoint; only the label
source differs.

| column | old (matcher) | new (labeller) |
| --- | --- | --- |
| critical recall (CR) | fraction of facts with a carrier (`fidelity` in faithful/partial/distorted) | fraction of facts with `status` present or partial |
| omission | 1 - CR | 1 - CR |
| complete coverage | fraction of traces with every fact carried | same, with `status != absent` |
| distortion / fidelity loss | distorted facts / carried facts | facts with `fidelity == distorted` / carried facts |
| aggregation failure (AF) | complete coverage AND answer not exact | same |

`answer_correct` is the matcher record's field (MuSiQue exact match), held
fixed across checkpoints. Traces with no facts are excluded from CR and
counted complete by construction; there are none in this population.

## Validation status and caveat

The labeller is validated for **carrier identification at the board
checkpoint only**, and only as cross-model agreement with Gemini 3.6 Flash,
not author ground truth. The redo therefore reports:

- **board rows as the validated column** (with the cross-model caveat);
- **extraction rows as exploratory** - the labeller has no validation at that
  checkpoint;
- **fidelity/distortion rows as unvalidated** - the V5 reference checked only
  whether a carrier exists, not its fidelity label. They are reported beside
  the matcher column and are not a correction of it.

The old matcher columns stay on record unchanged. The paper file is not
edited; the new columns sit beside the old ones in the report.

## Pilot and cap

A pilot of 20 instances per model (hash order `sha256('43|redo|'+instance)`)
at both checkpoints = **120 calls**, cap **$0.50**. If the calls parse and the
actual cost is in line, the remaining 4,680 calls run under a **$5.00** cap.
Every call logs an intent record before dispatch and a result record with
`cost_usd`; the run resumes from cached valid results.

## Analysis

For each checkpoint and model: CR, omission, complete coverage, distortion
rate and AF for old and new, with 95% CIs from an instance-cluster bootstrap
(seed 43, 2,000 draws; exact Clopper-Pearson for single proportions where
noted). Pooled rows are over all 2,400 traces. The report is written to
`report.md`; the call log is `calls.jsonl`.

## Answer equivalence

The MuSiQue answer-equivalence cells from
`rebuttal/pilots/20261113_musique_equiv/report.md` are reproduced in the
report as a separate table, **hand-checked by two readers, not
author-validated**. They are not applied to the Stage 2 AF column, because the
equivalence adjudication covers the earlier 400-call main-table set, not this
population.