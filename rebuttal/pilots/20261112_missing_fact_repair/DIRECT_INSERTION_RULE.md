# Direct-insertion pilot rule (frozen before any call)

Frozen 2026-11-12, before the first paid call. This is v1 of this arm; it is
reported beside the extraction-fix pilot and does not replace it.

## Question

If the missing fact is supplied directly to the board, does the final answer
become correct? This is an oracle upper bound on the repair mechanism, not an
achievable repair: a perfect re-extractor that delivered the exact claim would
be indistinguishable from this arm.

## Cohort

All 59 unique instances of the Stage 2 clean extraction-omission cohort, one
trace per instance. The trace is chosen by the frozen model order
`gemma31b`, `gpt4omini`, `qwen235b`; this is the same choice as
`presence.json`. The 33 present, 6 partial, and 20 absent instances are all
included; the presence label is carried into the report and results are split
by it.

## Arms

- **control**: the original board, unchanged, with the trace's own subject
  model, answer prompt, and scoring.
- **insert**: the original board plus one unit assigned to the E4-v7 target
  agent (`target_agent` in `presence.json`), with unit id `R-ins:0` and text
  equal to the instance's missing fact (`fact` in `presence.json`) verbatim.

No extractor and no delivery gate run in this arm: the fact is always
delivered. Both arms are called on every case in the run.

## Calls and scoring

- Answer calls use the frozen relay aggregation system prompt
  (`_AGGREGATION_SYSTEM`), `max_tokens=1024`, `temperature=0`, and the API
  model of the chosen trace.
- Scoring is the frozen exact rule: `answer_f1 == 1.0`, with the instance's
  answer aliases. No judge, no content match, no re-scoring of main tables.
- Every intent and result is appended to `calls.jsonl` with a `call_id`,
  model, token usage, and cost. The hard cap is $5 for the pilot; the full
  cohort is a separate run under the same cap and only after the pilot is
  reviewed.

## Pilot and full cohort

- Pilot: the first 10 instances in sorted instance-id order.
- Full cohort: all 59, after the pilot is reviewed. The full run calls only
  cases not already answered; pilot answers are reused unchanged.
- Report: control and insert exact counts with exact Clopper-Pearson 95%
  intervals, paired better/worse, the split by presence label (`present`,
  `partial`, `absent`), and cost.

## Interpretation fixed in advance

- The insert arm on the 20 absent instances is an oracle bound on what the
  board could do if it contained the fact. It does not repair a real
  extraction omission and is not evidence that the extraction stage can be
  fixed; those instances remain recorded as misdiagnosed.
- The insert arm on the 33 present instances is the relevant upper bound for
  the extraction-fix pilot: any gap between insert and repair is the cost of
  re-extraction plus the R2 gate.
- A high insert score with a low repair score means the board answerer can use
  a supplied fact but re-extraction does not deliver it.