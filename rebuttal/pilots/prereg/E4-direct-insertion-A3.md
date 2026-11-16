# E4 amendment A3 — direct insertion of the targeted fact (17 extraction cases)

Date: 2026-11-10. New file; `E4-v7.md` is not edited. This amendment adds one arm pair, R-ins and
V-ins, to the E4 extraction group. It does not change E4-v7, A1 or A2.

**Why this amendment exists, in plain words.** The Phase 1 outcomes have been read. The
re-extraction arm (R-ext) did not put the targeted fact on the board in 16 of 17 extraction cases:
by the matcher carrier check the fact was absent in 12, the carrier call failed in 1, and the fact
was present but the answer was identical to the Rerun in 3 (`E4_phase1/repair_effect_check.md`).
The extraction contrast therefore cannot be read as a repair effect. This amendment was added after
those outcomes were read, because the re-extraction arm did not deliver the fact.

## Scope

The 17 `extraction_omission` cases in the frozen action manifest
`rebuttal/pilots/20261110_e4_phase1/actions_phase1.json` (SHA-256 in the run config). No other
group, no distortion arm, no aggregation arm, no Phase 2.

## R-ins: direct insertion

For each case, take the targeted fact: the first fact in the frozen carrier list whose `extraction`
carrier array is empty (the E4-v7 target rule, `scripts/build_e4_manifest.py:68`). Its frozen text is
`facts.facts[].text` in the action manifest.

**Inserted span.** The frozen manifest holds no source quote for extraction targets: `target_span` is
frozen for distortion swaps only, and the atomic extraction facts are normalised statements, not
verbatim sentences of the source documents. The only verbatim fact-level span in the frozen manifest
is the fact text itself. R-ins therefore appends that exact frozen fact text, unchanged, as one new
board unit. This is a direct-insertion positive control, not a source-quote swap.

The unit has `unit_id` `R-ins:0`, `agent_id` equal to the frozen `target_agent`, and the text above.
It is appended after the existing board units, in that order. The board is then re-aggregated with
the same aggregator and settings as the Phase 1 Rerun: `original_prompt(record, board)`
(`_AGGREGATION_SYSTEM` and `_build_evidence_board_prompt`), temperature 0, seed 42, `max_tokens`
4096. No other field of the record or board changes.

## V-ins: equal-volume control

The control appends one new board unit with a verbatim passage from the frozen `donor_agent`'s
source context, chosen and truncated by this rule, fixed before any call:

1. `T` = exact base-tokenizer count of the R-ins text (`count_added_tokens`, no chat framing).
2. Split the donor's frozen source-context text into sentences at `(?<=[.!?])\s+` or `\n+`.
   Drop any sentence that starts with `Question:`, equals `You hold the following evidence:`, or
   starts with `[Document:`.
3. Enumerate every contiguous run of the remaining sentences, in original order, starting at a
   sentence boundary. Join the run's sentences with one space.
4. Accept a run if its token count is in `[0.9 T, 1.1 T]`. If the count exceeds `1.1 T`, remove
   trailing words one at a time until it is at most `1.1 T`; accept the truncated run only if it is
   still at least `0.9 T`.
5. Among accepted runs choose the one with the smallest `|tokens − T|`; ties by earliest start
   sentence, then fewest sentences. The chosen text is used verbatim, as one unit, with `unit_id`
   `V-ins:0` and `agent_id` equal to the frozen `donor_agent`.
6. If no run is accepted, the case is reported as "control cannot be matched" and is not scored;
   no substitute, padding or different donor is used.

The donor is the frozen `donor_agent` (first other board agent with no support-set fact; fallback
first other board agent, flagged `donor_fallback` in the manifest). The control can therefore carry
support content in fallback cases; the report states this per case and it is not repaired.

V-ins is aggregated exactly as R-ins. Both arms add exactly one unit, so the A1 `volume_match`
(equal added-unit count and ±10% added tokens) is the token test alone.

## Manipulation check

For each arm, a strict string check on the actual aggregator input: casefold the inserted span and
the aggregated user prompt, replace every non-alphanumeric character with a space, collapse
whitespace, and require the inserted span as one contiguous substring of the prompt. A case whose
R-ins or V-ins span fails the check is reported and not scored; both checks are shown per case.

## Budget, calls, failures

- 17 cases × 2 arms = **34 planned calls**; hard `--max-calls 34`; **cap $0.10**.
- One attempt per ledger record; a failed call is logged, unscored, and never retried. No call is
  dispatched after the cap.
- Paper models only, per case as frozen: `qwen/qwen3-235b-a22b-2507`, `openai/gpt-4o-mini`,
  `google/gemma-4-31b-it`. No model substitution.
- The config, this amendment and the frozen insertion plan are hashed before the first call.

## Analysis, after the report

Report first: case and call counts, failures, per-case manipulation check, per-case volume match and
any unmatched case, cost against the cap. Only then compute the contrast on cases that pass both
checks (both manipulation checks and volume match): paired R-ins minus V-ins correctness, 95%
percentile CI by instance-cluster bootstrap (2,000 draws, seed 42); descriptive when fewer than
5 pairs. No table or draft uses the numbers before they are sent to the lead.

No distortion arm and no Phase 2. Those still wait for the author swap check.