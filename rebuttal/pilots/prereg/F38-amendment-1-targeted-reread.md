# F38 amendment 1: targeted verbatim re-read and sentence-level presence (frozen before the re-run)

Written 2026-11-16, after the v0 Fix B and Fix C runs (kept in
rebuttal/pilots/20261116_f38_repairs/v0_untargeted_prompt/) and before any amended call.

## Cause found in v0 (stated before the re-run)

1. The Fix C "fact is in the owner's document" test compared the fact with the whole passage. The gate needs one
   sentence. Sentence-level, 4 of the 11 v0 "in document" facts are not stated (best sentence recall 0.57-0.71).
2. The re-read prompt asked for up to three sentences "that bear on the question", not the fact. When the fact was
   stated, the model often quoted other sentences, which the gate then rejected (2 of 11 delivered in v0).
   Fix A and Fix B used the same prompt for every distorted or absent fact, so they share the flaw.

## Amended steps (replace the v0 steps; everything else in the frozen rule stays)

- Presence test (Fix C only): the best recall of any single sentence of the owner's source passages to the fact is
  >= 0.8 (C1). Else any other agent's sentence >= 0.8 (C2). Else (C3). Sentences are split on sentence-final punctuation.
- Targeted verbatim re-read (Fix A, B and C): the system prompt is
  "You quote evidence verbatim. Copy sentences exactly as they appear; never paraphrase, summarise, or add words.
   If no sentence states the target fact, write NONE."
  The user message gives the passage, the target fact text, and asks to copy the sentence(s) that state the same claim,
  numbered 1..3, or NONE. The passage is the owner's source passage with the highest sentence-level recall to the fact.
- Delivery gate unchanged (recall >= 0.8, STOP list). Replacement and append rules unchanged.
- Answer step, control, scoring, and caps unchanged.

## Predictions, stated before the re-run

- Fix C: about 7 of 11 C1 facts will have a sentence-level match; the targeted quote should deliver for most of them.
- Fix A and Fix B: the verbatim re-read is reported as a separate step, so a no-delivery result is visible.
