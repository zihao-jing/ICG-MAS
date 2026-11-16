# Four-model strict-fidelity re-check under the clarified prompt (9f)

2026-11-15. Runs only because 9e passed on the relay population
(`Relay-strict-fidelity-validation-v3-enriched.md`, κ .791 [.466, 1.000], prompt v2). Cap **$0.5**.

## Purpose

One label should govern both populations. The four-model column was produced with
`strict_fidelity_pair_prompt_v1.json` (validated .992 / κ .937 against Opus on 120 pairs); the relay column now
uses `strict_fidelity_pair_prompt_v2.json`. This step re-labels the whole four-model pair population with the
v2 prompt, re-validates it against the **existing** Opus 5.5 reference labels (no new Opus calls), and recomputes
the strict and broad rates.

## Frozen inputs

- Population: `20261115_distortion_rescore/population_pairs.json` (1,328 pairs, four models), unchanged.
- Prompt: `strict_fidelity_pair_prompt_v2.json` (sha `fc725839…`), same as the relay v3 run.
- Label: `strict_fidelity_new_models_pairs` at the board checkpoint.
- Labeller: Haiku 5.5 (temperature 0, 2,500 output tokens). Reference: the Opus 5.5 labels recorded in
  `20261115_distortion_rescore/calls.jsonl` (`refg/*`), 120 pairs.
- Scoring: same definitions as the A4 run — strict = distorted / covered, broad = (distorted + partial) /
  covered, covered = labelled faithful, partial or distorted; Clopper-Pearson 95% intervals; validation with an
  instance-cluster bootstrap (2,000 draws, seed 43).

## Bars

The v2 label is registered for this population only if, on the 120 reference pairs, agreement >= .80 **and**
kappa >= .60. If it fails, the v2 rates are reported as measured but not registered, and the four-model column
stays on the v1 prompt.

## Cost

1,328 Haiku calls at the measured $0.000239 per call = about **$0.32**. No new Opus calls. Cap $0.5.