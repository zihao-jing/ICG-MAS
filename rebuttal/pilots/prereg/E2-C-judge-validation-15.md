# E2-C judge validation on 15 carded traces (frozen before any call)

Date: 2026-11-14. Stage: attribution scoring on released baseline outputs.

## Items

15 k = 1 traces from the frozen Part B validation set
(`rebuttal/pilots/20261114_part_b_k1/answers.jsonl`), zero-indexed rows
`126:141` (records 127–141), disjoint from the 7-trace E2-C casebook. The
first 10 (rows `126:136`) are already labelled in
`rebuttal/pilots/20261114_e2c_validate/`; this completion adds the last 5
(rows `136:141`). Two released methods on the Qwen-235B backbone: Who&When
all-at-once (MIT) and Who&When-Pro `all_at_once` (released 17-mode taxonomy).
10 new baseline outputs, 10 Opus calls, 10 Gemini calls = 30 calls.

The card's 15 reserved traces are the unit; the 10-trace prereg
`E2-C-judge-validation.md` is the frozen first stage and stays on record.

## Reference and candidate

Reference: Opus 5.5, labels frozen and hashed before the Gemini label exists.
Candidate: Gemini 3.6 Flash. Both see the rendered trace and the method's raw
answer, never each other's label, never the audit.

Prompt, system (frozen text, unchanged from `E2-C-judge-validation.md`):

> You are an annotator for a research study on multi-agent evidence flow. You
> will see ONE recorded run and one attribution method's answer. The answer
> names an agent and a stage (extraction, transmission or aggregation). Decide
> whether that (agent, stage) is a site of a visible evidence-flow defect that
> could be decisive for the wrong final answer. Judge only from the trace and
> the method's answer; do not use outside knowledge. If the answer is
> unparseable, or no defect is visible at that agent and stage, answer "no".
> If the evidence is insufficient, answer "uncertain". Reply with a single JSON
> object and nothing else:
> {"match": "yes|no|uncertain", "agent": null, "stage":
> "extraction|transmission|aggregation|null", "rationale": ""}

User template: `{trace}\n\nATTRIBUTION TO CHECK:\n{attribution}`.

## Bar

Agreement >= 0.80 and Cohen's kappa >= 0.60 on `match` (three categories),
with 95% CIs, computed over the combined 30 pairs (15 traces × 2 methods). The
10-trace labels are combined with the 5 new labels; no label is dropped or
relabelled. If the bar fails, the Gemini judge is unvalidated for E2-C and no
E2-C judge label is used; only agreement is reported.

## Budget

30 calls (10 new baselines + 10 Opus + 10 Gemini), cap **$1.00**. The existing
10-trace run cost $0.600179 and stays on record; this rule adds only the five
new traces. The gate must pass before any E2-C extension judge label is read.