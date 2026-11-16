# Gate v2a rule: content-token recall (frozen before any call)

Frozen 2026-11-12, before the first paid call of this version. This is a new
frozen version of the R2 delivery gate; v1 (`EXTRACTION_FIX_RULE.md`,
`src/audit/e4_fix_gates.py`) stays on record unchanged and is not replaced.

## Question

The v1 gate blocks verbatim sentences that state the claim because its recall
counts function words. Does replacing the recall term with content-token
recall deliver more of the same targeted extractions, without loosening the
structural protections?

## Change, and only this change

- v2a recall: the fraction of the fact's **content tokens** (fact tokens minus
  the frozen `STOP` set in `src/audit/e4_fix_gates.py`) that the text carries,
  as a multiset, must be >= 0.8.
- Kept unchanged from v1: empty text, question text, document header, refusal,
  and data-list fragment reasons; the 0.8 threshold; the cohort; the locator
  prompt; the answer prompt; the scoring rule.
- v2a is implemented in `src/audit/e4_fix_gates_v2.py`. v1's `delivery_gate`
  and `recall` are not edited.

## Inputs and calls

- Extraction inputs are the frozen v1 targeted-extraction outputs in
  `extraction_fix/delivery.json` (same 33 present instances, same locator
  prompt, temperature 0). **No new extraction call is made.** Reusing them is
  the point: v1 and v2a are compared on identical extraction output, so any
  difference is the gate.
- New answer calls are made only for cases that v2a delivers and v1 blocked.
  A v1-delivered case keeps its v1 repair answer (identical units).
- Board-only control answers are the frozen v1 `extraction_fix/answers.jsonl`
  board-only calls on all 33 cases (identical board, prompt, model). They are
  the paired control for both v1 and v2a; no new control calls.
- Answer calls: frozen `_AGGREGATION_SYSTEM`, `max_tokens=1024`, temperature 0,
  the trace's own model. Scoring: frozen exact `answer_f1 == 1.0` with aliases.
- Every new call is logged to `gate_v2a/calls.jsonl`; hard cap $5.

## Reporting

- Delivery under v1 and v2a on the same 33 cases, each with exact
  Clopper-Pearson 95% CI, and the list of cases v2a newly delivers.
- For the v2a-delivered set: exact answers with a 95% CI, paired against the
  reused board-only control on the same cases.
- Beside v1: v1's delivery 18/33 and repair 6/18, plus the paired control on
  v1's 18 delivered cases (0/18). v1 numbers are reported as they were.
- Right-content, exact-fail answers are listed separately, as in v1.

## Interpretation fixed in advance

- v2a is a gate change, not a new repair mechanism. Its deliverable cases are
  still the same oracle-targeted extraction; the comparison isolates the
  gate's function-word penalty.
- Content-token recall can admit a sentence that co-locates the entities
  without stating the relation. Delivery is therefore only a gate result; the
  exact answer score is the outcome.
- v1 remains the reported default until this pilot is reviewed. A v2a result
  does not replace v1 in any table.