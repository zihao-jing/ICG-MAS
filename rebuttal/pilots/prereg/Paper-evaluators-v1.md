# Paper evaluators against author labels on the E1 anchor (Paper-evaluators-v1)

Date: 2026-11-09. Status: written before any scoring call. Scope: the paper's own two evaluators, scored
on the same 90 anchor traces against the authors' fact-presence and fidelity labels. No new author
labelling. No existing pre-registration is edited; this file is the pre-registration for these runs only.

## Question

E1 so far validates the frozen semantic matcher and the rebuttal's reference judge (Gemini 3.6 Flash),
not the instruments that produced the paper's reported numbers. Here the paper's lexical coverage rule
and its alignment LLM judge are scored against author labels on the anchor.

## Which instrument the paper's coverage uses

The reported critical-fact coverage (CritRec) is computed with no semantic matcher and no LLM:
`scripts/compute_audit_metrics.py::align_gold_to_transmitted` aligns each gold unit to the candidate
unit with the best score, where score = max(numeric overlap fraction N, token Jaccard J) and
`covered = score > 0.0` (τ = 0, the paper default; `app_main.tex:238–258`, `3-methodology.tex:58–59`).
This is the path used by `scripts/exp2_extraction_quality.py` and `scripts/stage_wise_survival.py`, which
produce the reported CritRec figures. A second implementation exists in `src/audit/alignment.py`
(`align_units`, default `method="lexical"`), where the labels PARAPHRASE/PARTIAL/NO_MATCH come from
Jaccard thresholds 0.6/0.3 and `match_threshold=0.1`; its `method="llm"` option calls the alignment judge
with the prompt printed in `app_main.tex:405–428`. The reported CritRec tables use
`align_gold_to_transmitted`, not `align_units`, and no LLM. Both code paths are named here because the
paper text does not distinguish them.

## (a) Lexical coverage rule (deterministic, free)

Rule used unchanged: `scripts/compute_audit_metrics.py::align_gold_to_transmitted`, called with the
author's atomic fact text as the single gold unit and the checkpoint's candidate units as the
transmitted list. `_numbers_in_text` and the token sets are the function's own; τ is the code's
`best_score > 0.0`, i.e. the paper default 0. No line of that function or of
`_legacy_match` (`src/audit/critical_fact_validation.py`) is changed. Prediction: `covered` = the
checkpoint contains the fact under this rule. It is binary and cannot emit partial/distorted.

Target labels: the authors' board/pool fidelity label for that fact (collapsed to present = not
`absent`; and the 4-way fidelity with the structural restriction covered→faithful, not-covered→absent).

Rows: every author fact × checkpoint (pool, board) × author, on the 90 anchor traces; author
`uncertain` labels excluded. No mapping restriction is needed for a deterministic free rule.

## (b) Alignment judge (Qwen-235B, paper prompt, temperature 0)

Model: `qwen/qwen3-235b-a22b-2507` (the paper's alignment judge; temperature 0.0, `app_main.tex:669`,
`674`). Prompt text: the alignment-judge system and user strings exactly as printed in
`app_main.tex:405–440` (`Gold unit: {gold_unit}` / `Candidate unit: {candidate_unit}`). The code's
`src/audit/alignment.py::_judge_prompt` differs in two label words ("Gold evidence unit", "Candidate
transmitted unit"); this run uses the paper text, as instructed. Output: JSON only,
`{"label": "EXACT|PARAPHRASE|PARTIAL|DISTORTED|NO_MATCH", "confidence": 0.0, "reason": "..."}`.
One call per eligible row, no retry; schema-invalid or failed calls are logged and unscored.

Mapping rule, fixed before any call (deterministic, computed with no LLM):

1. Gold unit: the author fact has exactly one `source_ids` entry; that id must name one gold unit in
   `trace.source_supports`. Gold text = that unit's text. (Every anchor fact has exactly one.)
2. Candidate unit: the argmax of the same max(N,J) score over the checkpoint's units. A row is eligible
   only when the argmax is unique (no tie). Ties are excluded and counted.
3. No other source of a candidate unit is allowed; in particular the author's own carrier unit_ids are
   not used to pick the candidate (that would leak the label being tested).

Eligible rows and their author labels were counted deterministically before writing this file:

| Checkpoint | Eligible rows (unique argmax) | faithful | partial | absent | distorted |
|---|---:|---:|---:|---:|---:|
| pool (extraction) | 426 | 406 | 0 | 20 | 0 |
| board | 426 | 400 | 6 | 20 | 0 |
| total | 852 | 806 | 6 | 40 | 0 |

All 1,356 fact × checkpoint rows have exactly one gold unit; 504 rows have a tied argmax and are excluded.

## Collapse of the five judge labels onto the author labels (fixed before scoring)

| Judge label | Presence (primary) | Fidelity (4-way) |
|---|---|---|
| EXACT | yes | faithful |
| PARAPHRASE | yes | faithful |
| PARTIAL | yes | partial |
| DISTORTED | yes | distorted |
| NO_MATCH | no | absent |

Pre-registered sensitivity for presence: yes only for EXACT/PARAPHRASE (PARTIAL and DISTORTED count as
no). The primary collapse is the table above. No other collapse is computed.

## Statistics

Row-level, on the eligible rows above, weighted with the locked anchor weights w_h = N_h/n_anchor,h,
within-stratum instance-cluster bootstrap, 2,000 draws, seed 42, percentile 95% CI. Reported for each
of (a) and (b): accuracy, weighted Cohen κ, Gwet AC1, and the prevalence of the positive class beside
every κ. Author–author agreement on the same rows is reported beside them as the ceiling. The 4-way
fidelity κ is reported with the author-label distribution actually present (no distorted rows, 6 partial
rows); that limitation is stated in the reading, no class is added, pooled or imputed.

## Calls, cap, cost

- (a) zero calls.
- (b) 852 eligible rows, one call each; no deduplication (identical gold/candidate texts recur across
  authors, models and checkpoints; per-row labels are kept rather than shared).
- Estimated cost per call: about 300 prompt tokens (system ≈180; median gold+candidate 372 characters)
  and about 40 output tokens at the 2026-11-08 Qwen-235B snapshot price ($0.14/M prompt, $0.80/M
  completion), i.e. about $0.00008/call → full run about $0.07; hard cap $1.00 for the full run.
- Pilot first: 48 rows, stratified by checkpoint and author label (faithful/absent; all 6 partial rows
  included if the sample permits), fixed by seed 42; about $0.004. The full run starts only after the
  pilot log and counts are seen.

## Failures and exclusions

Failed or schema-invalid calls are logged and unscored with the reason; no retry and no `max_tokens`
change (cap 512). Missing rows are excluded from the denominators and counted. No author label is
edited. If more than a handful of calls fail, the run stops and reports.

## Not in scope

No held-out trace, no new author labelling, no change to any existing pre-registration, no recalculation
of any paper number. The paper's reported CritRec, OmissionRate, AggFail and distortion values are not
re-estimated here; this run only measures whether the two evaluators reproduce author labels on the
anchor.