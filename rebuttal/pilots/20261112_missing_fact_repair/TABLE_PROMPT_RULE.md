# Tabular extraction prompt rule (frozen before any call)

Frozen 2026-11-12, before the first paid call of this version. This is a new
frozen version of the locator prompt for tabular evidence; the v1 sentence
prompt (`EXTRACTION_FIX_RULE.md`) stays on record unchanged and is not
replaced.

## Question

Three v1 delivery failures are tabular evidence: the sentence locator returns
`NONE` because the claim is in a table row, not a sentence. Does a locator
prompt that accepts table rows and header labels, applied to the same 33
present cases, deliver the tabular cases without losing the sentence cases?

## Change, and only this change

- New frozen locator prompt (below), replacing the v1 sentence-only prompt.
  It asks for verbatim spans that may be table rows, and for the header(s)
  needed to read a row.
- Kept unchanged: the cohort (33 present instances, one trace each), the R2
  delivery gate **v1** (function-word recall) so the prompt is the only change,
  the answer prompt, the scoring rule, and the answer model.
- Applied to all 33 cases, not only suspected tables, so the prompt's effect
  on sentence evidence is measured rather than assumed. A routing rule would
  add a second unvalidated change.

## Frozen locator prompt

System:

    You are a careful evidence locator.
    You are given a question, a target claim, and a document.
    The document may contain prose or tables.
    Return up to 3 verbatim spans from the document that state or directly
    support the target claim. A span may be a sentence or a table row.
    Rules:
    - Copy each span exactly as it appears; do not paraphrase, merge, or add
      comments.
    - If the support is in a table, include the row and the column header or
      headers needed to read it, exactly as they appear.
    - Output a numbered list, one span per line.
    - If nothing in the document supports the claim, output exactly: NONE

User:

    Question: {question}

    Target claim: {fact}

    Document:
    {context}

    Return up to 3 verbatim spans from the document that state or directly
    support the target claim.

## Calls and scoring

- One locator call per case (33), on the target agent's own context only.
- Delivery with the unchanged v1 gate; then repair answer calls for every case
  the new prompt delivers (fresh, so the units match), each paired with the
  frozen v1 board-only control answer on the same case.
- Answer calls: frozen `_AGGREGATION_SYSTEM`, `max_tokens=1024`, temperature 0,
  the trace's own model. Scoring: frozen exact `answer_f1 == 1.0` with aliases.
- Every call logged to `tabular_prompt/calls.jsonl`; hard cap $5.

## Reporting

- Delivery 33-case count with exact 95% CI, beside v1's 18/33.
- The three tabular cases (`2hop__619265_45326`, `2hop__435184_84856`,
  `4hop3__131775_29339_508306_70744`) called out individually.
- Cases the new prompt delivers that v1 blocked, and cases it loses that v1
  delivered.
- Repair exact answers with a 95% CI and the paired board-only control on the
  same cases; right-content, exact-fail answers listed separately.

## Interpretation fixed in advance

- The prompt is oracle-targeted (the claim is given); the comparison is
  v1 prompt vs this prompt on the same 33 cases, gate and scoring held fixed.
- A gain confined to the three tabular cases with no sentence-case loss
  supports a tabular-specific locator. A loss on sentence cases says the
  prompt is not a drop-in replacement and would need routing, which is a
  separate change to be approved before any call.
- v1 remains the reported default until this pilot is reviewed.