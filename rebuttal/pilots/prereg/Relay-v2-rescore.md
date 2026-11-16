# Relay strict/broad rates under the v2 prompt

2026-11-15. Frozen before any call. Makes the relay distortion figures usable: the v2 prompt is validated on
this population (`Relay-strict-fidelity-validation-v3-enriched.md`, agreement .900, kappa .791 [.466, 1.000]),
and the rates must now be computed with that same prompt.

## Population

The frozen relay pair population `20261115_relay_rescore/population_pairs.json` — 945 pairs, 315 per protocol
(random relay, score-ranked relay, redundancy-aware relay). Unchanged.

## Label and models

`strict_fidelity_pair_prompt_v2.json` (sha `fc725839…`), Haiku 5.5 labeller, one fact and one unit per call,
temperature 0, 2,500 output tokens. No Opus calls: the reference labels used in validation already exist.

## Rates

- **Strict**: `fidelity == distorted` / covered, where covered = labelled faithful, partial or distorted
  (absent pairs are listed, not in the denominator).
- **Broad**: `fidelity in {distorted, partial}` / covered.
- Clopper-Pearson 95% intervals, per protocol and pooled.

The validated kappa .791 applies to this prompt only; the earlier step-9 prompt rates are not quoted.

## Cap

**$0.5.** 945 Haiku calls at the measured $0.00025 = about $0.24. Every call logged with intent and result
records.