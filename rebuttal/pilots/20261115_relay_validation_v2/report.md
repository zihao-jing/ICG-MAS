# Relay strict-fidelity validation v2 (clarified prompt)

2026-11-15. Rule `Relay-strict-fidelity-validation-v2.md` (sha `26a714b2…`), prompt `strict_fidelity_pair_prompt_v2.json` (sha `fc725839…`). 30 relay pairs (10 per protocol, seed 48, 0 shared with the v1 draw), Haiku 5.5 labeller, Opus 5.5 reference. Spend **$0.355546**, cap $0.5.

## Result

| quantity | value [95% CI] |
| --- | --- |
| distorted vs not, agreement | 1.000 [1.000, 1.000] |
| distorted vs not, kappa | nan [nan, nan] |
| three-class agreement | 0.967 |

Reference calls 0 of 30 distorted; labeller calls 0.

Bars: agreement >= .80 and kappa >= .60. **FAILS**. Wide-interval rule: does not apply.

| reference \ labeller | faithful | partial | distorted | absent |
| --- | ---: | ---: | ---: | ---: |
| faithful | 23 | 0 | 0 | 0 |
| partial | 1 | 5 | 0 | 0 |
| distorted | 0 | 0 | 0 | 0 |
| absent | 0 | 0 | 0 | 1 |

The kappa is undefined (NaN), not small: both sides call **0 of 30** pairs distorted, so the positive class is
empty and kappa has no variance to standardise. The 1.000 agreement is degenerate for the same reason — every
pair is faithful or partial, so "distorted vs not" agrees by construction. This is a different failure from
v1's kappa of 0: there the labeller had no positives while the reference had two; here neither side has one.

## What changed under the clarified prompt

| quantity | v1 (prompt v1) | v2 (prompt v2) |
| --- | ---: | ---: |
| three-class agreement | .833 | **.967** |
| reference partial → labeller faithful | 3 | **1** |
| reference distorted → labeller faithful/partial | 2 | **0** |
| reference distorted pairs | 2 | 0 |

The five v1 misreadings the fix was written for are gone: 5 of the 6 reference-partial pairs now agree and 1
remains partial→faithful (v1: 3 of 8), and no reference-distorted pair is misread. The diagnosis in v1 (Haiku accepted compressed numeric records as
faithful and called a mistyped digit partial) is consistent with the fix working; the residual disagreement is
`partial → faithful` on a compressed list unit, not the distortion boundary.

## Registration

Not registered. The bars cannot be met on this sample: kappa is undefined with 0 positives. The relay strict
rates stay unvalidated and the text may not quote them. The three-class agreement (.967, 30 pairs) is a
descriptive result only.

## Next step (not run, needs approval)

The pass bar is on a class that a random 30-pair relay draw almost never contains — the reference called 2/30
distorted in v1 and 0/30 here. A validation that can meet the bar needs distorted pairs in the sample:
either stratify toward pairs the old Qwen-235B judge labelled DISTORTED or non-faithful (the population has 3
old-judge distorted pairs, so the pool is small), or enlarge the random draw to ~150 pairs, where about ten
positives are expected at the four-model-set prevalence; about **$1.9** at the measured $0.012/pair. Re-using
the two v1 distorted pairs would leak the pairs that designed the fix and would not count.

## Ledger
Spend $0.355546. Cumulative from the global sum below.
