# Restore check: Sonnet 5.5 judge, Opus 5.5 adjudication (frozen before any call)

2026-11-16. Replaces the human labelling step for the restore test. Stage: final aggregation answers. Cap **$5.00** (Sonnet cap $2.00, Opus cap $3.00).

## Population

All answers of the restore pilot in `rebuttal/pilots/20261116_restore_equiv_gemini/restore_results.jsonl`, 184 rows:
- 92 restore-arm answers (the board with the verbatim source sentence in place of the garbled unit);
- 92 control-arm answers (the board with garbling kept).

Question and gold answer from `rebuttal/pilots/20261113_restore_source/cases.json` (joined by `key`; gold must match the restore-results gold after normalisation, checked in the script).

## Judges

1. **Sonnet 5.5** (`claude-sonnet-5-5`), all 184 answers. Local Claude Code CLI, headless print mode (`claude -p ... --output-format json`), run from an empty temporary directory, tools off, fixed system prompt file, `--exclude-dynamic-system-prompt-sections`. Output must be JSON `{"verdict": "correct"}` or `{"verdict": "incorrect"}`; the last JSON object with a valid verdict is taken. Invalid output is retried once; if still invalid it is recorded as invalid.
2. **Gemini 3.6 Flash checker** (existing): the verdicts already in `restore_results.jsonl` (EQUIVALENT = correct, NOT_EQUIVALENT = incorrect). Not re-run.
3. **Opus 5.5** (`claude-opus-5-5`), same CLI route as Sonnet, adjudicates only the answers where Sonnet and the Gemini checker disagree (verdicts of Sonnet and Gemini differ). Opus verdict is final for those answers.

User message to each judge: `QUESTION`, `GOLD ANSWER`, `SYSTEM ANSWER` (the answer text), as in `scripts/opus_checker_check.py`. The system prompt is the one written to `prompt.txt` in this folder before any call; its sha256 is in `build_manifest.json`.

## Final label and figures

- Final label = Sonnet verdict where Sonnet and Gemini agree; Opus verdict where they disagree.
- Restore figure = correct share of the 92 restore-arm answers under the final label; control figure = correct share of the 92 control-arm answers. Wilson 95% intervals. Paired comparison by McNemar exact test.
- Agreement of Sonnet with Gemini (raw, 184 answers) and Wilson 95%.
- On the disagreement answers: how often Opus sides with Sonnet and how often with Gemini.
- Opus is run only on the Sonnet-vs-Gemini disagreements, so Sonnet-vs-Opus disagreement is measured on that set: the number of answers where Opus's verdict differs from Sonnet's. If that number is more than 5, the labelling package (kept locally) is used for the disagreements; otherwise it is not used.

## Logs

Every call is logged to `calls.jsonl` with input and output tokens and cost. No call log is deleted.
