# Scoring rule for re-scoring the paper's main tables

Written 2026-11-12 **before any labeller call** for this task. The original
numbers stay on record and unchanged; every result here is written beside them.

## Scope

Pilot: **Qwen-235B only**, both benchmarks, the four protocols that have a
trace package from the existing run outputs:

| benchmark | runs | instances |
| --- | --- | ---: |
| Silo-Bench (SB) | `results/run_qwen235b_n5` (n=5) + `results/run_qwen235b_n10` (n=10), pooled | 52 |
| MuSiQue (MQ) | `results/run_qwen235b_musique` | 100 |

Protocols: `summary_exchange`, `random_relay`, `score_ranked_relay`,
`redundancy_aware_relay`. That is 4 x (52 + 100) = **608 traces**.

`full_sharing`, `single_local`, `majority_vote`, `best_local`,
`free_form_debate`, `confidence_gated` and `disagreement_gated` are outside the
pilot: the existing package builder does not reconstruct their board, and the
validated prompt reads a board. They are not scored here and their table cells
stay as they are.

The paper's other main tables (`tab_audit_combined`, `tab_audit_intervention`)
report audit metrics (critical recall, omission, distortion, redundancy,
useful-budget, aggregation-failure) that are not answer-correctness scores;
this rule does not touch them.

## Unit and inputs

One unit = one `(run, protocol, instance)` trace. The trace package comes from
`build_trace_packages` on the frozen run directory, so the question, gold,
source contexts, extraction pool, board and final answer are the same objects
the audit already uses. The final answer is `baseline_prediction`.

## Labeller

The **frozen validated v2 prompt** `labeller_prompt_v2.json`
(file sha256 `7f9e2816…`, system sha256 `585d0d45…`), model
`anthropic/claude-haiku-5.5` through OpenRouter, temperature 0, no reasoning.
It is the same prompt and model that scored agreement 0.953 [0.913, 0.987],
kappa 0.878 [0.760, 0.965] on the 150-trace validation set. Output is one JSON
object; the last complete object is used. Unparsed output is retried once at a
larger output budget, and every attempted call is logged.

The answer is judged correct when the labeller returns `CORRECT`; `DEFECT` is
wrong. This is the only change relative to the lexical rule.

## Lexical rule (the original scoring)

- SB: `silobench_exact_match(pred, {'answer': gold}) == 1.0`.
- MQ: exact token-F1 `answer_f1(pred, {'answer': gold}) == 1.0` under the
  project's current `normalize()`.

The paper's original cells are also reported unchanged: SB exact-match
accuracy and MQ mean answer F1, as stored in each run's `results.json`.

## Aggregates

- Cell accuracy (labeller) = mean of `CORRECT` over the cell's traces.
- Cell accuracy (lexical) = mean of lexical exact match over the same traces.
- MQ mean F1 (original and current) = mean `f1` over the same traces.
- SB cells pool `n5` and `n10`; MQ is the 100-instance run.
- Agreement and Cohen's kappa between the labeller and the lexical rule are
  reported per cell and pooled, with 95% cluster-bootstrap CIs (2,000 draws,
  seed 42; cluster = instance).
- Every pairwise disagreement is listed with question, gold, answer, lexical
  F1 and the labeller rationale.

## Spend and stopping

Pilot cap: **$2.00**. Every call is logged in
`rebuttal/pilots/20261112_rescore/calls.jsonl` (intent before dispatch, result
after). The runner stops before a call that could exceed the cap and reports
how many traces were left. No full run is started until the pilot is reviewed.