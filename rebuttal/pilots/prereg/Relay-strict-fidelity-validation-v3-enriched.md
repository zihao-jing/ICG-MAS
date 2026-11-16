# Relay strict-fidelity validation v3 (distortion-enriched sample)

2026-11-15. Follows the v2 rule (`Relay-strict-fidelity-validation-v2.md`, sha `26a714b2…`), which used the
clarified prompt and passed agreement but could not compute kappa because a random 30-pair relay draw
contained no reference-distorted pairs (0/30).

## What changes

Only the sample design. Label, prompt, models, bars and scoring are unchanged from v2:
`strict_fidelity_pair_prompt_v2.json`, Haiku 5.5 labeller, Opus 5.5 reference, one fact and one unit per
call, temperature 0, distorted-vs-not with an instance-cluster bootstrap (2,000 draws, seed 43).

## Sample (frozen before any call)

30 pairs from the frozen relay population (`20261115_relay_rescore/population_pairs.json`, 945 pairs):

- **15 enriched** drawn from the 30 pairs that **any prior label flags as distortion** — the old Qwen-235B
  judge's `DISTORTED` class (3 pairs) or the Haiku step-9 relabel's `distorted` class (29 pairs), union 32,
  minus the 2 that fall in the v1 design sample or the v2 validation sample, leaving 30.
- **15 controls** drawn from the remaining 834 pairs whose old-judge label is not `NO_MATCH`, equally at
  random.

Both draws use seed 49, ordered by `sha256('49|enal|' + pair_id)`. The sample file and its sha are written
before the first call; the rule, prompt and population shas are recorded in the build manifest.

**Enrichment is a property of the sample, not of the population.** The reported agreement and kappa describe
the label's behaviour on a sample where distortion is deliberately over-represented; any distortion rate must
come from the population run, never from this sample.

## Exclusion

Pairs in the v1 design sample are excluded because the prompt clarification was written from their
disagreements; pairs in the v2 sample are excluded because they have already been scored.

## Bars

Register `strict_fidelity_relay_qwen` under prompt v2 only if agreement >= .80 **and** kappa >= .60 on
distorted-vs-not, with 95% CIs. If the CI lower bound of kappa is below .40 the label is wide-interval and
stays out of the headline.

## Cap

**$0.5.** 30 Opus + 30 Haiku calls at the measured ~$0.012/pair, about $0.37. Every call logged with intent
and result records.