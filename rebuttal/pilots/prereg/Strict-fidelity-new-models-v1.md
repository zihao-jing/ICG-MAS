# Strict fidelity on the four new models' distortion pairs: rule v1

2026-11-15, frozen and hashed before any call. Re-scores the additional-model distortion rates in UEGh W2
(1.3%, 4.6%, 0.8%, 10.6%) with a validated label instead of the unvalidated Qwen-235B Dist judge.

## Population

- Silo-Bench, `score_ranked_relay`, n5 + n10 runs of Gemini-FL, GPT-4o-mini, DeepSeek-R1-32B and Gemma-4-31B.
- Pairs are built exactly as `scripts/run_distortion_new_models.py`: each gold shard is aligned to the
  transmitted units, and the best unit is kept when its alignment score is ≥ 0.05. That gives **1,328
  judge-eligible pairs** and reproduces the old run's totals (390 / 390 / 350 / 390).
- The old covered counts (378 / 349 / 123 / 356) are smaller because the Qwen judge also returned NO_MATCH
  on some eligible pairs. The analogue under this label is **absent** (the unit carries nothing). The rate's
  denominator is therefore the pairs labelled faithful, partial or distorted; absent pairs are counted and
  reported separately, and a fixed-denominator rate over all 1,328 eligible pairs is reported beside it.
- Source of the rates being replaced:
  `results/distortion_new_models/distortion_results.json`, produced by the
  Qwen-235B judge (EXACT / PARAPHRASE / PARTIAL / DISTORTED / NO_MATCH). That label is unvalidated.

## Label

- Prompt `strict_fidelity_pair_prompt_v1.json` (sha recorded): the v10 strict-fidelity system text verbatim,
  one critical fact (the gold shard) and one entry (the aligned transmitted unit) per call.
- Fidelity classes: faithful / partial / distorted / absent, exactly as the v10 prompt defines them. A pair is
  **distorted** when the unit contradicts the gold shard's central claim.
- Labeller: Claude Haiku 5.5. Reference: Opus 5.5. Identical prompt, temperature 0.
- Rate: distorted pairs / covered pairs, 95% Clopper-Pearson interval, beside the old Qwen rate.

## Validation before use

- 120 eligible pairs, 30 per model, taken evenly across each model's score-ordered pairs; the sample
  is in `validation_sample.json` with its sha. (The reference is Opus 5.5, which is reasoning-billed; 120
  calls keep the validation and the full Haiku re-score inside the $4 cap.)
- Agreement and κ on **distorted vs not** (the quantity the rate uses) and on the 3-class fidelity label,
  each with a 95% instance-cluster bootstrap CI (2,000 draws, seed 43).
- Bars: agreement ≥ .80 and κ ≥ .60. Register the label only if both pass. If they fail, stop: do not run
  the full re-score, read the disagreements, report the cause and the next fix.

## Cap and logging

Cap **$4.0** for the validation and the full Haiku re-score together; every call logged; stop if the running
projection would exceed the cap. No tuning of the prompt on the validation pairs.