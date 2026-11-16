# Paper-evaluator validation v1.1 — lexical rule on all rows; judge on the mapped rows

**Version note.** v1.1 is a separate pre-registration written before its numbers were computed. It
changes exactly one thing from `Paper-evaluators-v1.md` (SHA-256
`1efdd85bd00eb67250a80eaf164c551934df75eea9b1289b0f65da23176baf68`): **the lexical rule (a) is scored
on all 1,356 fact × checkpoint × author rows**, because it needs no gold-to-candidate mapping, and is
reported apart from the 852 judge-eligible rows. Nothing else changes: the lexical rule, the mapping
rule for the judge, the five-label collapse, the sensitivity version, the prompt, the model, the
settings and the statistics are those of v1.0 and are restated here unchanged.

Date: 2026-11-10. Written and hashed before any full-run call and before the tie counts below were
computed.

## Why this amendment

v1.0 scored the lexical rule only on the 852 rows with a unique lexical argmax. 504 rows are tied at
the checkpoint maximum and were excluded. If those ties are rows where every candidate unit scores 0,
then the exclusion removes exactly the rows on which the lexical rule says "not covered", and part of
the reported degeneracy would be a selection effect rather than a property of the rule. v1.1 therefore
scores the lexical rule on the full 1,356 rows and reports the 852-row subset separately.

**Tie reporting (descriptive, fixed here before the counts are computed).** A tied row is **all-zero**
if its maximum checkpoint lexical score is exactly 0.0 for every unit, and a **positive tie** if the
maximum is above 0.0. Counts are reported by checkpoint (pool / board) and by author fidelity label,
for all 1,356 rows and for the 852 eligible rows. Tie status is not changed and no row moves between
the eligible and tied sets.

## Data and scope (unchanged from v1.0)

The 90 anchor traces scored by the matcher, 30 instances, three models; the authors' fact-presence and
fidelity labels from the returned E1 anchor files, used as they are (decided 2026-11-09; file SHA-256 in
`rebuttal/results/batch1/UNSEAL_AUTHORISATION.md`). No new author labelling. The anchor weights, strata
and cluster bootstrap are those of `E1-v9.md`: 2,000 draws, seed 42, within-stratum instance-cluster,
percentile 95% CI, weighted by the locked anchor weights.

## (a) Lexical coverage rule, unchanged

`scripts/compute_audit_metrics.py::align_gold_to_transmitted`, called exactly as the paper's critical-fact
coverage calls it: `covered = score > 0.0` with the paper's default τ = 0.0. The file is not edited for
this analysis. The rule is deterministic and makes no model call. It is applied per candidate unit at
the checkpoint and the checkpoint is *covered* if any unit is covered; the per-row prediction is the
same function's `covered` value already computed in `scripts/run_paper_evaluators.py::rows()`.

Scoring set: **all 1,356 rows**. The 852 judge-eligible rows are reported separately, and the
difference between the two sets is the 504 tied rows.

## (b) Alignment judge, unchanged, judge-eligible rows only

Qwen-235B (`qwen/qwen3-235b-a22b-2507`), temperature 0, seed 42, `max_tokens` 512, JSON object, one call
per row, no retry; the prompt printed in `app_main.tex:405–440`, prompt hash
`66ef5e82…` as frozen in v1.0.

Mapping rule (unchanged): an author fact maps cleanly when its `source_ids` names exactly one gold unit
and the checkpoint's lexical scores have a unique argmax; the candidate is that argmax unit. Rows with
no single gold unit or with a tied argmax are not called. Mapping coverage is a deterministic count and
uses no LLM call.

## Collapse and sensitivity (unchanged)

Pre-registered collapse: `EXACT` and `PARAPHRASE` → faithful/present; `PARTIAL` → partial/present;
`DISTORTED` → distorted/present; `NO_MATCH` → absent/absent. Sensitivity, fixed in v1.0 and reported
beside it: strict presence counts `EXACT`/`PARAPHRASE` only.

## Statistics

For each evaluator against the authors: accuracy, weighted Cohen κ (three-way presence; four-way
fidelity), Gwet AC1, and the author-label prevalence, each with the 95% CI from the same bootstrap.
The judge reports both collapse versions. The author–author ceiling from the E1 analysis is repeated
beside them. The label mix limits what can be claimed: 806 of 852 eligible rows are faithful and no
eligible row is distorted, so the fidelity κ has a wide CI by construction. Nothing here validates the
paper's numbers; agreement is reported descriptively.

## Full run (this amendment authorises it)

852 calls, cap `max_calls` 852 and **$1.00**, every call logged by the append-only ledger, failed or
unparseable calls logged and unscored, no retry. Stop at the cap. The lexical rule costs nothing and
is computed deterministically after the run.

Code: `scripts/run_paper_evaluators_full_v11.py` (wrapper over the v1.0 runner functions, same prompt,
mapping and collapse), analysis `scripts/analyze_paper_evaluators.py`. Config
`rebuttal/pilots/configs/Paper-evaluators-v1.1.json` records this file's SHA-256.