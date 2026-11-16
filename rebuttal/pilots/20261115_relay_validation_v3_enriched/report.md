# Relay strict-fidelity validation v3: distortion-enriched sample

2026-11-15. Rule `Relay-strict-fidelity-validation-v3-enriched.md` (sha `356c250a...`), prompt `strict_fidelity_pair_prompt_v2.json` (sha `fc725839...`). 30 relay pairs: **15 pairs flagged as distortion by a prior label** and **15 controls**, seed 49, excluding the v1 design sample and the v2 sample. Haiku 5.5 labeller, Opus 5.5 reference. Spend **$0.391206**, cap $0.5.

## Result

| quantity | value [95% CI] |
| --- | --- |
| distorted vs not, agreement | 0.900 [0.767, 1.000] |
| distorted vs not, kappa | 0.791 [0.466, 1.000] |
| three-class agreement | 0.867 |

Reference calls 13 of 30 distorted; labeller calls 10. Bars: agreement >= .80 and kappa >= .60.
**PASSES** Wide-interval rule does not apply.

| reference \ labeller | faithful | partial | distorted | absent |
| --- | ---: | ---: | ---: | ---: |
| faithful | 12 | 0 | 0 | 0 |
| partial | 1 | 2 | 0 | 0 |
| distorted | 0 | 0 | 10 | 3 |
| absent | 0 | 0 | 0 | 2 |

## Enrichment

The prior flags came from the old Qwen-235B judge (`DISTORTED`, 3 pairs) and the Haiku step-9 relabel (`distorted`, 29 pairs); 30 usable pairs remained after excluding the v1 and v2 samples. The draw is 15 of those and 15 controls, so distortion is over-represented by construction. **Agreement and kappa here describe the label on this enriched sample; any distortion rate must come from a population run, not from this sample.**

## Registration

Registered as `strict_fidelity_relay_qwen` v3-enriched (prompt v2).

## Ledger
Spend $0.391206.

## The three disagreements

All three are `distorted -> absent`: the reference finds an entry that carries the fact and contradicts it,
the labeller finds no carrier at all and returns absent. The binary quantity counts these as disagreements
(distorted vs not). They matter for a strict distortion rate, whose denominator is *covered* pairs: a pair the
labeller calls absent leaves the denominator, so the effect on a rate is smaller than the 3/30 suggests, but it
is not zero and it is the direction that understates distortion.

The five v1 misreadings (compressed records accepted as faithful, a mistyped digit called partial) do not
recur: `faithful -> faithful` 12/12, `partial -> partial` 2/3, and no distorted pair is called faithful or
partial.
