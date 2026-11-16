# Coverage prompt v2 validation on held-out author labels

Frozen 2026-11-13, before any call. This validates `coverage_prompt_v2.json`
against author labels that the earlier validation did not use, and writes the
pass rule down before the run. It does not change any earlier result.

## Why held-out

`COVERAGE_VALIDATION_RULE.md` (v1) validated on the 90 E1 **Anchor** traces in
`rebuttal/pilots/20261112_labeller/validation_150.jsonl`. The returns under
`rebuttal/annotation/labelling_20261108/returns/E1*.json` contain 115 E1 items.
The **25 items not in `validation_150.jsonl`** are the held-out population:
Dev runs 01-20 (two annotators each) and Calibration runs 1-5 (four annotators
each). They were not used by the v1 validation, by the 120-trace re-score, or
by the writing of prompt v2.

## Population and comparisons

25 E1 items, **60 author comparisons** (20 Dev items x 2 + 5 Calibration items
x 4). The trace and both label files come from the returns themselves; the
Calibration items therefore have four independent labels, not two.

## Author-side coverage (fixed before calls)

For one annotator and one trace, coverage is **complete** iff every critical
fact in that annotator's `critical_facts_json` has at least one
`carriers_json` entry with `checkpoint == "board"` and `fidelity == "faithful"`.
A fact with only partial, distorted or absent board carriers, or with no board
entry, makes the comparison incomplete.

## Prompt-side coverage

`coverage_prompt_v2.json`, Claude Haiku 5.5, temperature 0, `max_tokens` 2000,
one attempt per trace. Supports and board rendered by the same function used in
the v1 validation and in the Track 1 pilot. The prompt's `complete` (every
support `present`, where a support may be carried jointly by several units) is
the statistic compared to the author-side label. The prompt is not shown the
answer.

## Pass rule (written before the run)

The v2 labeller **passes** only if, on the 60 held-out comparisons:

1. raw agreement is **at least 0.80**, and
2. Cohen kappa is **at least 0.60**.

If either fails, the coverage labeller remains **not validated**, the lexical
rule remains the reported coverage figure, and no prompt edit is made after
seeing the result. If both hold, v2 is reported as validated on held-out author
labels with its exact Clopper-Pearson agreement interval and its kappa
interval, and the lexical figure stays beside it as the paper's existing
measure.

## Endpoints

Raw agreement, exact Clopper-Pearson 95% CI on agreement, Cohen kappa, prompt
and author complete rates, per-item results, and every disagreement with the
prompt's per-support status and reason. Cap **$5**, every call logged with
intent and result.

No full run, no paper edit, no commit.