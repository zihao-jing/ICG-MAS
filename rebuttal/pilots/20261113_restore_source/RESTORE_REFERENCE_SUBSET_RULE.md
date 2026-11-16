# Restore comparison on the reference-gated subset (frozen before any call)

Written 2026-11-13, before any new answer call. This rule adds a subset
analysis to the restore-the-source run; it does not change the 184-case run,
the 132 figure, or the frozen `RESTORE_RULE.md` / `RESTORE_FULL_ADDENDUM.md`.

## Subset

The **92 held-out cases** (of the 144 confirmer-validation cases) on which
the independent Gemini 3.6 Flash reference says `source_states_fact = yes`
and the candidate source sentence is verbatim in the source shard. This is
the reference gate from `confirmer_validation_report.md`; its 92/144 count is
frozen there. The keys are written to `reference_subset_cases.json` with
their sha256 in `reference_subset_manifest.json` before any new call.

Of the 92, **90 already have control and restore answer arms** in the frozen
full-run `results.json` (they are also Haiku-confirmed cases). **2 are
reference-only**: the confirmer said `source_states_fact = no`, so the full
run did not answer them. Those two keys are
`565f46cecca4` (4hop1__399219..., gemma31b) and `8177d5cd79b4`
(4hop1__391525..., qwen235b). They are included exactly because the frozen
reference gate, not the confirmer, defines this subset; including them
without new arms would drop the reference's stricter positives.

## New calls

For the 2 cases without arms, run the same two aggregation arms as the full
run: the unchanged board (`control`) and the board with the confirmed source
sentence substituted at the distorted unit (`restore`). The aggregation
model is **Claude Haiku 5.5** (`anthropic/claude-haiku-5.5`), temperature 0,
`_AGGREGATION_SYSTEM`, `_build_evidence_board_prompt`, `max_tokens=1024` -
identical to `restore_source_pilot.py`. Four calls total (2 cases x 2 arms).
Cap **$0.25**; every call logs intent and result with `cost_usd` to
`reference_subset_calls.jsonl`. The 90 reused arms cost $0.000000 in this
run and are cited from the frozen full-run log.

## Frozen analysis

- Paired exact-match comparison on all **92** cases: control exact k_c/92,
  restore exact k_r/92, each with an exact Clopper-Pearson 95% CI.
- Paired difference `k_r - k_c` with a case-level bootstrap 95% CI (seed 43,
  10,000 draws: resample the 92 pairs with replacement, recompute the
  difference).
- Counts improved / worse / same.
- Report beside the 132-case result; the 132 stays on record unchanged.

## Caveats to carry into every use

- The reference is an LLM applying the same written prompt, **not author
  ground truth**. The 92 is reference-gated, not author-validated.
- The 132 figure remains confirmer-gated as before; this subset is an
  additional, stricter-positive analysis, not a replacement.
- The 2 reference-only cases enter on the reference's call alone; report them
  separately so the reuse of 90 is visible.
- The answer arms are a single aggregation call on a fixed board; this is the
  same descriptive comparison as the full run, not a deployable repair.