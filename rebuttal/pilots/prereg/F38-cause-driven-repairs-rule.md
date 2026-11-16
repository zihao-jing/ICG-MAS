# F38: cause-driven repairs (frozen before any call)

Written 2026-11-16, before any API call in this folder. Cap: $10 per fix. Subjects: the paper models
(gemma31b = google/gemma-4-31b-it, gpt4omini = openai/gpt-4o-mini, qwen235b = qwen/qwen3-235b-a22b-2507).
Opus is not used. The answer step uses each case's own paper model; the restore test used Haiku 5.5, so
the aggregator change is the setup fix in Fix A.

## Flags (the audit's own per-fact carrier labels)

Matcher record `rebuttal/results/batch1/expansion_stage2/matcher/*.json`, field `carriers`. Board fidelity per fact:
present = a board unit with fidelity faithful or partial; distorted = a board unit with fidelity distorted (and no
faithful/partial unit); absent = neither. Unit ids are the matcher's `board:aX:uY`.
Owner of a fact = the agent in its `source_ids` (`gold:agent-k` -> k).

## Common steps

- Board = the trace's board (`packages(model)[instance]['checkpoints']['board']`).
- Verbatim re-read (amendment-5 prompt, `VERB_SYSTEM`, `verb_user`): the owner's source passage with the highest
  recall to the fact; up to 3 units; a unit is delivered if `delivery_gate` passes (recall >= 0.8, STOP list). Unchanged 0.8 gate.
- Replacement: a distorted fact's board unit is replaced by its first delivered unit (or by the confirmed source
  sentence, for the restore fact in Fix A). An absent fact's delivered units are appended under its owner.
- Answer: the case's paper model, `_AGGREGATION_SYSTEM`, `_build_evidence_board_prompt`, 1,024 tokens.
- Control: the same paper model on the unchanged original board (so the control and repair share the aggregator).
- Scoring: primary = Gemini 3.6 Flash answer-equivalence checker (frozen prompt `answer_equiv_v1.json`, verdict
  EQUIVALENT); secondary = strict answer F1 = 1.0. Intervals: Wilson 95%.

## Fix A: 51 unfixed garbled-message cases (restore arm, Haiku aggregator)

Cause groups, from the matcher flags:
- A1, 31 cases: one garbled fact, no other flagged loss. Cause: the restored board has every fact present, so the
  unfixed result is the Haiku aggregator in the restore test. Fix: restore sentence, paper-model answer.
- A2, 8 cases: two or more garbled facts. Cause: other garbled facts still on the board. Fix: restore the first,
  verbatim re-read of each other garbled fact, paper-model answer.
- A3, 3 cases: an absent fact and a garbled fact. Cause: the absent fact was never restored. Fix: restore, verbatim
  re-read of the absent fact (appended) and of each other garbled fact, paper-model answer.
- A4, 9 cases: no matcher record. Cause unknown from the flags. Fix: restore sentence, paper-model answer, reported as a separate group.

## Fix B: 17 re-read cases, fact came back, answer still wrong

Cause from the flags of the trace (the fact that came back is the cohort's absent fact, so it is not counted again):
- B1, 15 cases: no other flagged loss. Cause: the answer step did not use the delivered fact. No further loss
  to re-read, so no repair is applied; reported as not applicable.
- B2, 2 cases: another garbled fact remains. Fix: verbatim re-read of each garbled fact, replacing its unit, paper-model answer.

## Fix C: 27 re-read cases, fact never came back

First step: is the fact in the owner's document (best sentence of the owner's source passage has recall >= 0.8)?
- C1, 11 cases: yes. Fix: verbatim re-read from the owner's passage (delivered units appended), paper-model answer.
- C2, 1 case: fact in another agent's passage. Reclassified as a sharding (routing) case by the audit's rule; not re-run.
- C3, 15 cases: fact in no passage under the 0.8 rule. Reclassified as extraction (absent at extraction) by the
  audit's rule; not re-run.

The reclassification counts are reported as they stand; C2 and C3 are not repaired.
