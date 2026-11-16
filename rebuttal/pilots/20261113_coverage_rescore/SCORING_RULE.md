# Coverage and aggregation-failure re-score — rule frozen before any call

Date frozen: 2026-11-13. Pilot only; no full run until review.

## Question

The paper's audit calls a task "complete coverage" when the lexical matcher
scores CritRec = 1, and counts it as a candidate aggregation failure (AF) when
coverage is complete and the answer is not perfect. This pilot re-scores the
same traces with two coverage scorers side by side:

- **lexical** — the frozen token rule below, computed on the board only;
- **labeller evidence flow** — the frozen `coverage-v1` prompt, which sees the
  question, the gold supports and the board and never sees the answer.

The answer side is identical for both scorers and comes only from the frozen
exact rule (`answer_f1 == 1.0`); the labeller is never used to score answers.

## Population

The 608 Qwen-235B traces in `rebuttal/pilots/20261112_rescore/cases.jsonl`
(both benchmarks, four protocols). Pilot sample: 30 traces per protocol,
chosen by ascending `sha256("43|" + key)` within each protocol (120 traces).
The sample is a pilot, not an unweighted population estimate.

## Lexical coverage

Normalise with `src.eval.evaluate.normalize`, strip the stopword list from
`scripts.pilot_llm_labeller` (STOP), and compare each gold support with every
board unit. A support is present when its best board unit carries at least
0.80 of its content tokens. Coverage is complete when every support is
present. A distorted carrier is not detectable lexically and is counted as
present, which is the known limitation of the proxy.

## Labeller coverage

Frozen prompt `coverage_prompt_v1.json` (Claude Haiku 5.5 through OpenRouter,
temperature 0, no reasoning tokens). The prompt receives the question, the
gold supports labelled `s1..sn`, and the board units with unit ids; it returns
one status per support (`present`, `partial`, `distorted`, `absent`).
Coverage is complete when every support is `present`; `partial` and
`distorted` count as incomplete. No answer text is shown. To bound cost, each
support is truncated to 6000 characters and each board unit to 1500 characters
in the rendered prompt; the truncation is recorded in the call log.

## Endpoints

- complete-coverage rate under each scorer, with exact Clopper–Pearson 95% CI;
- agreement and Cohen's kappa between the two complete-coverage labels;
- AF under each scorer = complete coverage and `answer_f1 < 1`, reported as a
  count and as a share of all pilot traces (the paper's denominator), with
  exact 95% CI;
- per-protocol breakdown;
- cost, every call logged with intent and result.

## Guardrails

Pilot cap **$5**, hard stop before any call that would exceed it; one attempt
per trace, no retries; temperature 0; the prompt and this rule are hashed into
`run_manifest.json` before the first call. No full run and no paper edit.