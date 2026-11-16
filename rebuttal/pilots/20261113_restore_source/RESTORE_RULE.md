# Frozen rule: restore-the-source test on real-run distortion diagnoses (item 4)

Written 2026-11-13 before any call. Stages: relay checkpoint (the distorted
board unit) and final aggregation (the answer arms). Pilot cap $5; every call
logged.

## Population

All real-run distortion diagnoses: the Stage 1 and Stage 2 matcher records
whose frozen `diagnosis` is `distortion` (38 + 176 = 214 traces, 184 unique
instances). One trace per instance, the first in the frozen model order
`gemma31b, gpt4omini, qwen235b`, gives 184 cases. Pilot sample: 40 cases,
sorted by `sha256('43|restore|' + instance_id)`; the rest wait for review.

## Source restoration

For the case's distorted fact (the first fact whose board carrier has
fidelity `distorted`) and its source shards (the `source_contexts` whose
`context_ids` are in the fact's `source_ids`), the candidate source sentence is
the sentence with the highest content recall to the fact (the frozen presence
rule's tokeniser and STOP set). This is the verbatim source text the audit says
the board changed.

## Labeller confirmation

One Claude Haiku 5.5 call per case, temperature 0. The input is the question,
the critical fact, the candidate source sentence, and the distorted board
unit; no other board content and no answer. The labeller returns strict JSON:

`{"source_states_fact": "yes|no", "board_contradicts": "yes|no", "reason": "..."}`

A case is **confirmed** only if `source_states_fact = yes` and the candidate
sentence is verbatim in the source shard (normalised substring). A confirmed
case is the only one restored. `board_contradicts` is recorded but is not part
of the confirmation (the matcher already labelled the unit distorted).

## Arms (confirmed cases only)

Two aggregation calls with Claude Haiku 5.5, temperature 0, identical board
prompt and unit count:

- **control (Rerun)**: the original board.
- **restore (R-source)**: the same board with the distorted unit's text
  replaced by the confirmed source sentence.

The aggregation model is fixed to Haiku 5.5 in both arms so the contrast is the
board content, not the model. This does not reproduce the original trace's
model; it is a board-content test. The final answer is extracted with
`extract_answer`; scored exact against the stored gold and with answer F1.

## Outcomes

- Confirmation rate over the pilot with an exact 95% interval.
- Among confirmed cases: exact before/after, paired improvement, F1 change.
- Cost per confirmed case and a projection to the remaining 144, reported but
  not run.

## Decision

If the confirmation rate is below 0.20, the restore test is reported as a
diagnosis-validity finding (most real-run distortions are not restorable
source contradictions), not as a failed repair. If it is higher, the paired
recovery is the repair evidence. Either way no paper cell is replaced and no
full run starts before review.