# Stage attribution on known-stage cases (item 6)

Rule `COMPARISON_RULE.md` (sha256 `0db054fa6449`), frozen before the comparison. Zero model calls; spend $0.000000. Stages: sharding, extraction, relay checkpoint, final aggregation.

## Injected distortions (30, truth = relay checkpoint)

| method | correct | accuracy (95% CI) |
| --- | ---: | --- |
| audit | 30/30 | 100.0% (88.4-100.0) |
| baseline | 0/30 | 0.0% (0.0-11.6) |
| always aggregation | 0/30 | 0.0% (0.0-11.6) |

The audit's 30/30 here is **by construction**: the injected unit is the one the diagnosis names, so this set measures the baseline against a fixed audit label, not the audit's accuracy.

## Missing-fact cohort (59, truth from the presence rule)

| method | correct | accuracy (95% CI) |
| --- | ---: | --- |
| audit old | 39/59 | 66.1% (52.6-77.9) |
| audit new | 59/59 | 100.0% (93.9-100.0) |
| baseline | 39/59 | 66.1% (52.6-77.9) |
| always aggregation | 0/59 | 0.0% (0.0-6.1) |

Against the older truth "extraction for all 59": audit old 59/59, audit new 39/59, baseline 59/59.

## Reading

The audit's **30/30 and 59/59 are consequences of the same rule that defines the stage**: the injected unit is the diagnosis by construction, and the cohort truth is the presence rule the item-9 check applies. They show the rule is applied consistently, not that the audit is accurate. The lexical-drop baseline uses the same checkpoints but no critical-fact labels; it cannot see a one-unit distortion that leaves most support tokens intact, and it has no input-presence check, so it misses the relay and sharding cases. The comparison is descriptive: it shows what the critical-fact labels and the input check add on these cases, and is not an independent accuracy estimate for the audit.
