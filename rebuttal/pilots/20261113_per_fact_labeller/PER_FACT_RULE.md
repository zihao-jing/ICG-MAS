# Frozen rule: per-fact labeller at the relay checkpoints

Written 2026-11-13 before any paid call. Stage: relay checkpoints (extraction
pool and shared board). Pilot cap: **$5 total**; every call logged.

## What the labeller is asked

One call per trace and checkpoint. The input is the audit's critical-fact list
(the matcher facts derived from the gold supports, read from
`rebuttal/results/batch1/E1_matcher_anchor/matcher/`) and that checkpoint's
entries. The support documents are **not** shown. The question is shown only to
disambiguate the fact list.

For every fact the labeller returns:

- `status`: `present` if the fact is recoverable from the union of the cited
  entries (it may be split across entries; no single entry need restate it),
  `partial` if only a fragment is carried, `absent` if none is.
- `fidelity`: `faithful` if the union states the fact with the same entities,
  values, relations and qualifiers, `partial` if a necessary qualifier is
  missing, `distorted` if the union contradicts the fact, `absent` if there is
  no carrier.
- `unit_ids`: every entry that is part of carrying the fact; text that only
  shares topic words does not count.

Only the shown question, facts and checkpoint entries may be used; no outside
knowledge; the final answer is not shown and must not be discussed.

## Authors' combining rule

Complete coverage is the authors' rule: every listed fact has a board carrier
with fidelity `faithful`. The labeller's complete label is `true` iff every
audit fact has board fidelity `faithful`. Extraction-pool completeness is
reported separately but does not enter the pass rule.

## Population and split (frozen before any call)

Traces: the E1 anchor records for which (a) the frozen matcher status is `ok`
and (b) the author return exists, i.e. 78 traces over 26 instances x 3 models.
Each trace has two author annotations with `author_complete` in
`rebuttal/annotation/labelling_20261108/returns/E1*.json`.

Instances are split within stratum after sorting by
`sha256('43|perfact|' + instance_id)`, using fixed quotas: for a stratum of
size n >= 8, tune = n//2, validation = round((n - tune) * 0.6), reserve = the
rest; n = 3 gives 1/1/1; n = 2 gives 1/1/0; n = 1 gives 1/0/0. The split is
written to `split.json` and hashed in the run manifest before the first call.

- **tune** 13 instances: the only traces whose author labels may be read while
  the prompt is revised.
- **validation** 8 instances: one run of the frozen prompt; the pass rule is
  applied here, once.
- **reserve** 5 instances: untouched unless validation fails. If it fails, the
  disagreements are read, the cause fixed in a new prompt version, and that
  version is validated once on the reserve. The reserve is never used for
  tuning.

If validation and reserve are both exhausted, no clean held-out author labels
remain in the anchor; a further validation would need new author annotation and
is not simulated with the tuning labels.

## Tuning and freeze

Prompt revisions run on the tune split only. Each revision is a new
`per_fact_prompt_vN.json`; the prompt file and system hash are recorded before
its run. The final prompt is frozen with its own hash in the run manifest
before the validation call set starts.

## Pass rule (fixed before the run)

At the trace x annotator level on the validation split:

- agreement `>= 0.80`, and
- Cohen's kappa `>= 0.60`.

95% intervals: exact Clopper-Pearson for agreement; instance-cluster bootstrap
for kappa (`sha256('43|perfact|kappa')`-seeded, 10,000 draws, 2.5/97.5
percentiles). The same rule applies to a reserve re-validation.

A call whose output is not strict JSON with every fact exactly once and the
allowed status/fidelity values is invalid; it is excluded from the paired
agreement and reported. If more than 10% of a validation split's calls are
invalid, the validation is void and the prompt is discarded, not scored.

## Outcomes

- Pass: the per-fact labeller is validated for the board complete-coverage
  label, and the main-table coverage, critical-recall, omission, fidelity and
  aggregation-failure columns may be redone with it, old values kept beside.
- Fail: the labeller is not validated; lexical coverage remains the reported
  figure. The disagreements are read and the cause is stated; a new prompt
  version is validated once on the reserve only.

## Amendment 1 (written 2026-11-13, before any validation call)

The first tuning pass used the matcher's atomic facts and returned tune agreement
0.603 (47/78 board comparisons, kappa 0.221; extraction 0.603/0.189). Reading
the disagreements showed the cause is the **fact list**, not the prompt: 31 of
78 board comparisons were labeller-incomplete/author-complete and none were
reverse. The matcher decomposes a source into atomic claims (e.g. "the
character named after the trochophore"), while the author `critical_facts_json`
entries are the source snippets themselves (e.g. an actor-character table row)
and the author label is defined per that list. A trace cannot be complete under
both lists at once.

The per-fact population is therefore one row per **(trace, annotator)** and the
fact list is that annotator's `critical_facts_json` from
`rebuttal/annotation/labelling_20261108/returns/E1*.json` — the list the E1
coverage label is defined on, and the audit's critical-fact input at that
checkpoint. The support documents are still not shown. `author_complete` is the
same list's carrier rule. The matcher-fact pass stays on record (artifacts
`population_v1_matcher_facts.json`, `results_v1_matcher_facts.json`) and is not
scored against the pass rule.

Split, prompt semantics, cap, pass rule and the two-stage validation are
unchanged. Per-fact status/fidelity is also compared with that author's carrier
record for the same fact and checkpoint and reported (descriptive; not in the
pass rule).

OpenRouter Claude Haiku 5.5 at $0.10 / 1M input and $0.50 / 1M output tokens;
cost per call from the response's usage, logged in `calls.jsonl`; running total
and cap enforced before each call.