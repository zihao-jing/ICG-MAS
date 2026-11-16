# Part B step 2: Opus via CLI on the 30 validation traces

2026-11-15. Rule `Part-B-step2-truth-rule.md` (sha `d2448fd0...`), prompt `E2-judge-v2.json`. Opus 5.5 through `claude -p`, API-equivalent cost $2.2663 (CLI charge $2.2286), cap $2.50 (amendment 1, sha `5068f74a...`).

| quantity | value |
| --- | ---: |
| traces | 30 |
| class agreement | 0.767 [0.600, 0.933] |
| kappa | 0.462 |

The class columns are the original single/multiple call. Transport deviation: this route is the local CLI, not the OpenRouter API; per-call costs use the API-equivalent price and the CLI charge is shown beside it.


## Verdict: negative

**Step 2 fails its bars.** Class agreement is .767 [.600, .933] and kappa .462, both below .80/.60. The cause is
the class labels themselves: on the multi-stage traces the two labellers agree on the defects but disagree on
whether one correction suffices, so `single` against `multiple` is the disagreement, not the stage. The stage-level
"30/30" is not a second, independent result.

## The stage-level row is withdrawn

The earlier 30/30 row is removed: its valid-stage set was the stored Gemini label's own defect list scored
against the Opus-CLI run, and the step-1 premise was built from the two labels read against each other. In the v2
set both sides list identical defect sets, so it was agreement by construction. No claim rests on it.

## Fix proposal

Replace the set-valued truth with **independent set-valued labels**: two annotators (Haiku 5.5 and a second
paper model, Opus as reference only if a third read is needed) label each of the 30 traces with the full set of
stages that fail, blind to both methods' outputs, under a frozen prompt and the existing atom/presence evidence;
hash the prompt and the adjudication rule before any call. Score each method by set agreement with the
annotator set: any-overlap (primary) and Jaccard (secondary), with a κ on the binary "names a valid stage", and
the same .80/.60 bars. Estimated cost: 30 traces × 2 annotators = 60 calls at about $0.006 each (Haiku) plus
30 reference calls at about $0.03 (Opus) ≈ **$1.3**, within a $2 cap. Step 3 stays blocked until that passes.

## Ledger
API-equivalent $2.266340; CLI $2.228619.
