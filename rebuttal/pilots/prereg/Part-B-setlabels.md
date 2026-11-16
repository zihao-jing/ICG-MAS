# Part B: independent set-valued stage labels (frozen before any call)

2026-11-15. Replaces the withdrawn 30/30 truth rule. Cap **$1.50**. No claim from any earlier stage-rule result.

## Population

The 30 fresh validation traces of the frozen k = 1 manifest (`extra/fresh_items.json`), rendered exactly as in
`Part-B-judge-v2.md`.

## Labellers, blind to both methods

- **L1:** Gemini 3.6 Flash.
- **L2:** Qwen-235B-A22B-2507.
- **Reference:** Opus 5.5 through the local `claude -p` CLI, same prompt, used to adjudicate set disagreements
  and to report between-labeller agreement.

Each labeller gets the trace and the question and returns the **set of stages at which the trace fails**:
`{"stages": ["extraction"|"sharding"|"transmission"|"aggregation", ...], "reason": "..."}`. No stage is
assumed. Labellers do not see the audit, the judge, or each other.

## Scoring

- Reference set per trace = the union of L1 and L2 stages where they agree; where they disagree, the Opus
  reference read decides.
- A method is scored by **any-overlap** (primary: names at least one stage in the reference set) and **Jaccard**
  (secondary: size of intersection over union), each with a Clopper-Pearson interval on the trace-level
  proportion.
- Bars, unchanged: agreement ≥ .80 and κ ≥ .60 on the binary any-overlap call against the labeller reference;
  the two labellers' agreement on that binary is reported as the reference's own reliability.

## Budget

90 calls: 60 cheap labeller calls (~$0.06) and 30 Opus CLI calls (~$0.9 API-equivalent). Hard cap $1.50,
call-level enforcement. Opus is labeller/reference only.
## Amendment note (after the run)

The v1 run stopped at $1.524 API-equivalent, **$0.024 over the $1.50 cap** — a breach: the last call's estimate
landed just under the remaining budget. The run is withdrawn: the reference included Gemini, the judge's own
model, so its overlap is circular. No claim from it. Superseded by `Part-B-setlabels-v2.md`.
