# Q1 30-case proxy set: gold definition amendment 1 (frozen before any call; 2026-11-16)

Amends `Proxy-gold-merge-v1.md` and the stage rule of `20261115_q1_second_sample` for the gold side only. Proxy labels are not changed.

## Why

The 30-case gold stage (`20261115_q1_second_sample`) read only `gold_supports[0]`, the first hop's paragraph. Each trace has 2 or 3 gold supports (16 with 2, 14 with 3). For 26 of the 30 traces the gold answer appears in some support but not in the first one, so the gold stage tested sentences that do not bear on the answer.

## Gold definition (replaces the earlier gold)

1. Answer-bearing sentence: a sentence of any of the trace's gold supports whose content tokens contain the gold answer's content tokens at recall >= 0.8. Content tokens use `normalize` from `src/eval/evaluate.py` with the `STOP` list from `src/audit/e4_fix_gates.py`; recall is the same `recall` function used by the word-matching gate.
2. Gold atoms: the answer-bearing sentences, split as `atoms_of` splits them (`scripts/q1_second_sample.py`), de-duplicated in order of appearance.
3. A trace with no answer-bearing sentence is not scored. It is reported as not scoreable, with its count.
4. The gold answer is the `gold` field in `results/run_qwen235b_musique*` for that instance.

## Labeller and stage rule (unchanged)

- Labeller: `google/gemini-3.6-flash`, the same labeller as the 7/30 re-label (`scripts/gold_side_rescore.py`), with no reasoning flag set.
- Prompt: `rebuttal/pilots/prereg/per_fact_points_prompt_v1.json`, unchanged (the validated point prompt).
- Checkpoints: extraction, then board only if no gold atom is absent at extraction.
- Stage: extraction if any gold atom is absent at extraction; else transmission if any is absent at the board; else aggregation.
- Proxy stage: the earlier Haiku 5.5 labels, unchanged.

## Opus reference (extraction checkpoint, every scored trace)

- Reference: `claude-opus-5-5` through the claude CLI only (empty temporary directory, tools disabled, the same prompt as system prompt, JSON output).
- Cap: $1.00 total, hard stop before each call. Each call is logged with the API-equivalent cost and the CLI-reported cost.

## Pass bars (fixed before the run)

Against Opus 5.5 on the extraction checkpoint, stage level (absent vs not absent), over the scored traces:
- agreement >= 0.90;
- Cohen's kappa >= 0.75.

Atom-level agreement is reported but is not a pass bar.

## Outcome

- If both bars pass, Q1 uses the new proxy-vs-gold agreement, with one disclosure line that the gold side is re-labelled by Gemini 3.6 Flash and checked against Opus 5.5 on the scored traces.
- If either bar fails, Q1 keeps 6/30 (Haiku labels, earlier gold).
- The 7/30 result from the first-support gold is reported in the source comment only.

## Outputs

`rebuttal/pilots/20261116_gold_answer_bearing/`: `build_manifest.json` (this amendment's sha), `calls.jsonl`, `results.jsonl`, `score.json`.
