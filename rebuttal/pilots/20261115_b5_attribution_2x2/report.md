# B5 (1/2): Gemini-backed matcher validation — FAILS, 2x2 not run

2026-11-15. Rule `B5-attribution-2x2.md` (sha `0441ed1c…`), frozen before the scored calls. Validation on 20
(model, instance) pairs disjoint from the 89 known-stage cases (seed 44), reference = the frozen Qwen matcher
record's own diagnosis on the same instance. Spend **$0.373055** (cap $0.5), plus one transport test call
$0.008070. **The 2x2 run has not started** — the frozen rule stops it on a validation failure.

## Result

| quantity | value [95% CI] |
| --- | --- |
| stage agreement (5 classes) | **.316** [.105, .526] |
| Cohen's kappa | **.012** |
| scored cases | 19 of 20 (one Gemini matcher run failed after retries) |

Bars: agreement >= .80 and kappa >= .60. **FAILS.**

| reference (Qwen) \ Gemini | extraction | sharding | transmission | aggregation | uncertain |
| --- | ---: | ---: | ---: | ---: | ---: |
| aggregation (10) | 3 | 0 | 1 | 6 | 0 |
| transmission (3) | 3 | 0 | 0 | 0 | 0 |
| extraction (1) | 0 | 0 | 0 | 1 | 0 |
| uncertain (6) | 2 | 0 | 0 | 3 | 0 |
| sharding (0) | 0 | 0 | 0 | 0 | 0 |

## Diagnosis, read from the logged records

- **Fact generation, not the carrier transport or parser.** All 43 calls succeeded (40 first attempts + 3
  retries, no failed call in the ledger except one case that exhausted its 3 attempts). The parser and schema
  validators accepted every returned object.
- **The fact sets differ, and the diagnosis is sensitive to the fact set.** The two backbones generate their
  own facts from the gold supports. In `gemma31b/3hop2__573858…`, Gemini generated three facts, carried two of
  them faithfully at extraction and board, and found no carrier for the third; its support set then requires
  the missing fact, so `diagnose_with_sharding` returns extraction omission. Qwen's fact set for the same
  instance did not contain that fact, so its diagnosis was transmission. Same trace, same checkpoints,
  different facts → different stage.
- **The disagreements are one-directional.** Gemini names `extraction` where Qwen says transmission
  (3 of 3) or uncertain (2 of 6), and names `aggregation` where Qwen says uncertain (3 of 6). It never
  reproduces a Qwen `transmission` label; the audit's transmission stage is the one most dependent on which
  facts the backbone chose to generate.
- **The sample is aggregation-heavy** (10 of 20 reference labels), which alone would make kappa fragile, but
  the failure is not a prevalence artifact: raw agreement is .316.

## What this means for the 2x2

Swapping the matcher backbone does not swap a labelling step — it swaps the facts the audit reasons about.
The Gemini-backed audit is therefore a *different attribution procedure*, not the audit with another model.
The 2x2 can only be run as designed if the audit column is defined to hold the fact set fixed and swap only
the carrier labelling; otherwise the row would compare "Qwen audit" against "a Gemini-fact audit" under the
same name.

Three options, all needing a decision:

- **A.** Redefine the audit row: freeze the Qwen facts, run the carrier step with each backbone, and validate
  that on a disjoint set (carrier presence per fact, bars .80/.60). That is a true backbone swap of one step,
  and the validation is cheap (about $0.1 on 20 cases). The 2x2 then compares two carrier backbones.
- **B.** Run the 2x2 descriptively with the Gemini audit built from its own facts, labelled as a different
  procedure, and report the .316 agreement as the reason the two audit columns are not comparable.
- **C.** Drop the Gemini audit column; run only the judge row's backbone swap (Qwen judge vs the existing
  Gemini judge), and report the audit column as Qwen-only.

## Ledger

Spend $0.381125 in this directory ($0.373055 validation + $0.008070 transport test). Cumulative from the
global sum.
