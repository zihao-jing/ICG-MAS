# Amendment 1 to Stage-naming-A3-fact-named-v1 (build-bug correction; rule text unchanged)

2026-11-16. Amends the fact-table build only. The A3 rule text (`Stage-naming-A3-fact-named-v1.md`, sha256 d8ac0cac79df66867ffdd35db7d188c843caa3cfa9e7c7d940a5c8589ba817b8) is not changed. The naming rule, the 0.8 match threshold and the 82-run population are not changed.

## What was wrong

`scripts/f39_fact_tables.py` read model output with plain `json.loads` / `ast.literal_eval`. Gemini carrier outputs wrapped in a fenced ```json block were rejected and counted as "no carrier record". This is a parser fault in the build, not a missing model output.

## Correction

- `scripts/f39_fact_tables.py --strict` parses with `src/audit/matcher_v2.py::strict_parse`, the parser the audit pipeline itself uses (strips a ```json fence; rejects duplicate keys).
- It writes `rebuttal/pilots/20261116_stage_naming/fact_tables_strict.json`.
- The original `fact_tables.json` is kept unchanged (verified byte-for-byte after the build).
- Same inputs, same match rule, same attempt rule (attempt-1 only, as before).

## Effect (checked on the table)

- Newly matched runs: `inj/gemma31b/3hop1__617062_127905_80286` (gemini) and `inj/gpt4omini/2hop__804417_126089` (gemini).
- Runs lost: none.
- Still unmatched after the correction: `inj/qwen235b/3hop1__144439_443779_52195` (gemini), `inj/gpt4omini/4hop1__93963_170667_443779_52195` (gemini), `inj/gemma31b/4hop1__151903_5274_458768_33677` (gemini). Under the frozen attempt-1 rule these have no parseable attempt-1 carrier output. See the note below.

## Note on attempts (not changed by this amendment)

The frozen build uses attempt 1 only. For `144439` (gemini), attempt 1 and attempt 2 are truncated, attempt 3 parses under strict_parse. For `93963` and `151903`, no attempt parses. Using attempt 3 for `144439` would be a change to the attempt rule; it is not made here and is raised for a decision.

## Scoring

A3 is rescored on `fact_tables_strict.json` with the same frozen rule (hash checked against d8ac0cac…). The original score `a3_score.json` is kept. The corrected score is written to `a3_score_strict.json` and labelled as a build-bug correction.

## Decision A (2026-11-16)

Run `inj/qwen235b/3hop1__144439_443779_52195` (gemini) stays unmatched under the frozen attempt-1 rule. Attempt 3 was chosen by the pipeline's own retry after the fact, so using it would add a selection rule that is not in the frozen build. The run is disclosed as unmatched (one of 82). Corrected A3 counts: named 49/53 (17+13+8+11), matched 53, excluded 29.
