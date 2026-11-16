# Part B main run (frozen before the first baseline call)

Date: 2026-11-14. Stage: released-method attribution and judge labelling on
the 126 k = 1 main-run traces.

## Population

The first 126 traces of `20261114_part_b_k1/answers.jsonl`, frozen with their
boards and answers. No trace is added or dropped after this point.

## Method calls

Who&When all-at-once (MIT), Who&When step-by-step (same release, stops at the
first error), Who&When-Pro `all_at_once` with the released 17-mode taxonomy,
and MAST, on Qwen-235B and Gemini 3.6 Flash. Temperature 0, max output 4,096.
Per trace this is 4n + 10 calls. The Gemini-backbone rows are separate and
marked "judged by the same model".

## Judge

Gemini 3.6 Flash, `E2_B` prompt from `rebuttal/judge/judge_prompts_v3.json`,
on the k = 1 trace. The Part B validation against Opus 5.5 gave class
agreement 0.800 and kappa 0.595 [0.267, 0.864] on 30 traces, below the
pre-registered kappa bar of 0.60. The judge is therefore **unvalidated for
this label**; the main table reports agreement only and says so. The main run
proceeds under that label because the card states it does.

## Batching

Three batches, capped at $3.80, $3.80 and $3.40. A batch stops at its cap and
the next starts only after review. Total cap $13.00. Any failed call stops the
batch for review; no automatic retry.