# Part B set labels, v2: majority of three independent labellers (frozen before any call)

2026-11-15. Cap **$2.00**. Replaces the withdrawn v1 reference (Gemini was the judge's own model).

Labellers: Gemma-4-31B, Qwen-235B, GPT-4o-mini. None is the judge, so the reference is independent of the Gemini
judge labels. Each returns the set of failing stages, blind to the methods. Reference set = stages named by at
least two of the three. Opus 5.5 through the CLI adjudicates only traces where no stage has a majority (issues a
set); it is a reference, not a subject. Rescores the 21 completed traces and runs the 9 missing.

Scoring unchanged from v1: any-overlap (primary) and Jaccard (secondary), .80/.60 bars on the binary call,
Clopper-Pearson interval, and the three labellers' pairwise agreement reported as the reference's reliability.
Every call's cost is projected before sending; a call that would exceed the cap is skipped.
