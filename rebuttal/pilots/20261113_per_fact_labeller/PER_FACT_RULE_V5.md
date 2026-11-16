# Frozen design: independent-reference fresh validation of the per-fact labeller

Written 2026-11-13 after the V4 check was rejected as validation. No call has
been made under this design; the reference labels it requires are not yet
produced. This file fixes the design before any reference label or labeller
call. V1-V4 stay on record unchanged.

## Why V4 does not count

In V4 the corrected references were made after the labeller output was seen,
and 40 of the 64 rows are E1 dev rows used in labeller development. Its
original-label result is the validation result and it fails: 47/64 = 0.734
(0.609-0.837), kappa 0.279 (0.000-0.577). The labeller stays unvalidated for
carrier identification. The post-hoc corrected-label 64/64 is an audit, not a
pass.

## Population (never used for tuning)

Traces from the MuSiQue main-table corpus not used anywhere in labeller
development: not in the 26 E1 anchor instances, not in the E1 dev or
calibration runs, not in the reserve or the V4 set. The main-table packages
available here are MuSiQue (800 instances x 3 models), so the check is
MuSiQue-only; that is also the domain of the reserve failures. Sample 60
unique instances by `sha256('43|v5|' + instance_id)`, one model per instance
chosen by the same hash, one board checkpoint per trace. No trace is added or
replaced after the sample is drawn.

The fact list for each sampled trace is the frozen audit matcher's
critical-fact list for that trace (`facts` in the matcher record), not the
authors' list and not a list chosen after seeing the board.

## Reference labels: fixed before any call, rubric applied independently

The reference labeller is **Gemini 3.6 Flash** (`google/gemini-3.6-flash`,
OpenRouter, temperature 0), using the frozen prompt file
`v5_reference_prompt.json` (file and system hashes recorded in
`v5_build_manifest.json` before its first call). It is neither the labeller
under test (Claude Haiku 5.5) nor the assistant that wrote this rubric.

It applies the written rubric below to the sampled board units and the matcher
fact list, without seeing any labeller output for these rows and without using
the V4 corrected labels. The labels are written to `reference_labels_v5.json`
and hashed before the first Haiku labeller call; the manifest records the hash
and `recorded_before_labeller_calls: true`.

Rubric (same carrier rule as V4, applied blind):

- A unit carries a fact if its text states the fact's claim, allowing
  paraphrase, reordering and entity aliases, but not a different entity,
  value, date, relation or qualifier. A fact split over units may be carried
  jointly.
- A fact with no such unit has an empty carrier list.
- A row is complete iff every fact has a non-empty carrier list.

Reference reliability: a second reader independently labels a 20-board
subsample; agreement and kappa between the two readers are reported. If
reader-reader kappa is below 0.60, the reference is reported as uncertain and
no pass/fail is claimed.

## Labeller and outcome

Prompt v3, unchanged (same file and system text); one call per sampled board.
The labeller's complete call is compared with the reference complete call.
Pass: agreement >= 0.80 and Cohen's kappa >= 0.60, with exact
Clopper-Pearson interval for agreement and instance-cluster bootstrap for
kappa (seed 43, 10,000 draws). Per-fact carrier agreement is reported beside
it.

This validates carrier identification only, not semantic fidelity or
coverage. The main-table coverage, recall, omission, fidelity and AF columns
stay lexical or matcher. No result from V1-V4 is retracted.

## Cost and stopping

At most 60 labeller calls, projected under $0.10, hard cap **$5**, every call
logged; stops and reports if the cap is reached. Reference labelling and the
second-reader check cost $0. No call is made under this design until the
reference labels are frozen and the design reviewed.