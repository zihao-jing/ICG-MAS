# Frozen rule: per-fact carrier labeller, corrected-label fresh validation

Written 2026-11-13, after the reserve audit, before any call on this set.
Supersedes nothing: `PER_FACT_RULE.md` (semantic target, FAIL),
`PER_FACT_RULE_V2.md` (carrier target, n=48 exploratory) and
`PER_FACT_RULE_V3.md` (reserve check, FAIL) stay on record unchanged.

## What the reserve audit found

All 10 reserve disagreements are author-citation errors, not labeller errors:
in each, the board units the author cited do not state the fact
(`author_citation_audit.md`). The labeller's `absent`/`partial` calls match the
board text. The labeller prompt is therefore unchanged; the ground truth is
corrected.

## Correction rubric (applied to every fresh disagreement)

For each (trace, annotator, critical fact), the author's cited board units are
read against the board text.

- A unit **carries** the fact if its text states the fact's claim, allowing
  paraphrase, reordering and entity aliases, but not a different entity,
  value, date, relation or qualifier. A fact split over several units may be
  carried jointly.
- If no cited unit states the claim, the citation is an **author error**: the
  corrected carrier list is empty for that fact, and `corrected_complete` is
  false for the row.
- If at least one cited unit states the claim, the original citation is kept;
  the corrected carrier list is the subset of cited units that state the claim.
- A fact whose recorded text is a truncated source fragment (ends mid-clause)
  is judged on the claim its visible text states; a unit that only names the
  topic is not a carrier.
- Corrections are made on the fresh set by applying the rubric to every
  labeller-author disagreement after the fresh calls, as on the reserve. Rows
  where author and labeller agree keep the author label. The original author
  labels stay in the population file and are reported beside the audited ones.
- Limitation, stated in the report: the candidate disagreements are found from
  the labeller's output, so a row where author and labeller are wrong in the
  same way is not corrected and counts as agreement. The audited label is
  read from the board text, not copied from the labeller, but the set is not
  an independent author re-annotation.

## Fresh set

Author-labelled traces not used in tuning, in the n=48 carrier rescoring or in
the 5-instance reserve: the four unused E1 anchor instances
(`I-02_n5`, `II-13_n10`, `III-24_n5`, `III-27_n5`; 24 board comparisons) and
the 20 E1 dev runs (40 board comparisons), 64 in total. SB anchor labels are
excluded because their carriers are a single flat unit list at the extraction
pool, not per-fact board units.

## Labeller and outcome

Prompt v3, unchanged (same file, same system text); one call per (trace,
annotator, board). Target: the board units that state each fact. Labeller
complete = every fact has a returned unit intersecting the corrected carrier
list and status not `absent`.

Pass: agreement >= 0.80 and Cohen's kappa >= 0.60, with exact
Clopper-Pearson interval for agreement and instance-cluster bootstrap for
kappa (seed 43, 10,000 draws). Reported beside the original author labels.
This validates carrier identification only, not semantic fidelity or coverage;
the main-table coverage, recall, omission, fidelity and AF columns stay
lexical or matcher.

## Cost and records

One call per comparison at most, cap $5, every call logged in
`calls_fresh.jsonl`; report `fresh_report.md`. The earlier results and labels
stay unchanged; no paper cell is replaced and no paper file is edited.
## Outcome note (2026-11-13, after review)

This design does **not** count as a validation. The references were corrected
after the labeller output was seen, and 40 of the 64 rows are E1 dev rows used
in labeller development. The validation result is the original-label
comparison: 47/64 = 0.734 (0.609-0.837), kappa 0.279 (0.000-0.577), FAIL; the
labeller stays unvalidated. The corrected-label 64/64 is reported only as a
post-hoc audit in `fresh_report.md`. A valid design is frozen in
`PER_FACT_RULE_V5.md`; it has not been run.
