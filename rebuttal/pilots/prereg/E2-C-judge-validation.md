# E2-C judge validation against Opus 5.5 (frozen before any call)

Date: 2026-11-14. Stage: attribution scoring on released baseline outputs.

## Items

10 k = 1 traces from the frozen Part B validation set (traces 127-136 in the
`answers.jsonl` order), disjoint from the 7-trace E2-C casebook. Two released
methods on the Qwen-235B backbone: Who&When all-at-once (MIT) and Who&When-Pro
`all_at_once` (released 17-mode taxonomy). 20 baseline outputs, 20 calls.

## Reference and candidate

Reference: Opus 5.5, labels frozen and hashed before the Gemini label exists.
Candidate: Gemini 3.6 Flash. Both see the rendered trace and the method's raw
answer, never each other's label, never the audit.

Prompt, system (frozen text):

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
with 95% CIs. Labels are frozen before the Gemini call. If the bar fails, the
Gemini judge is unvalidated for E2-C and no E2-C judge label is used; only
agreement is reported.

## Budget

40 judge calls plus 20 baseline calls. Cap **$1.00**. Opus priced at $4 / $20
per million tokens; Gemini at $0.75 / $3.75; Qwen at the preflight price.