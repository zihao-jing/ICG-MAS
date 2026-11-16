# Frozen rule: second reader for the MuSiQue hand-check

Written 2026-11-13 before the calls. Stage: final aggregation output. Cap $5;
every call logged. The first hand-check (73/74 equivalent) stays on record and
is labelled **hand-check, unvalidated** until this check is in.

## Sample

The 74 distinct exact-wrong / check-equivalent cases. Force-include the case
the first reader called not equivalent (`d9eca5f22c03`,
`3hop1__64957_87694_64412`, gold "11 February 1929", answer "1929") and take
23 more sorted by `sha256('43|second|' + key)`. 24 cases.

## Reader

Gemini 3.6 Flash via OpenRouter, temperature 0 with reasoning enabled (the
endpoint requires it). It is shown the question (recovered from the Stage 2
package), the gold answer and the system answer; it is **not** shown the
answer-equivalence prompt's verdict, its reason, or the first reader's verdict.
It returns strict JSON:

`{"equivalent": "yes|no", "reason": "one short sentence"}`

Under the same written rule as the first check: same entity, value, relation or
set; extra context, formatting, numeral/word form, title, spelling or a common
abbreviation allowed; missing decisive content is not equivalent.

## Decision

- The hand-check is reported as validated only if the second reader agrees with
  the first reader on at least 0.90 of the sample **and** confirms the one
  not-equivalent case.
- Otherwise the 51.2% figure stays labelled "hand-check, unvalidated" and is
  not used as a corrected cell.

Cost: 24 calls, cap $5, ledger in this directory.