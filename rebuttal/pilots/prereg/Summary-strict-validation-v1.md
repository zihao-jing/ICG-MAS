# Summary-exchange strict-fidelity validation, v1 (stratified sample) — frozen before any call

2026-11-15. Cap **$0.50**. Tests whether the validated strict-fidelity label (`strict_fidelity_pair_prompt_v2.json`,
registered on relay pairs as `strict_fidelity_relay_qwen` v3-enriched) also holds on summary-exchange pairs. The summary
figures in the rebuttal (strict distortion and omission) are cited only if this passes.

## Population

The 390 summary pairs of `rebuttal/pilots/20261115_summary_rescore/population_pairs.json`, labelled by Haiku 5.5 with the
same prompt (`calls.jsonl`, key `labh/<pair_id>`).

## Sample (frozen before any call)

30 pairs, stratified by the existing Haiku label: **10 distorted, 7 partial, 7 faithful, 6 absent**. Within each stratum
the pairs are ordered by `sha256('49|sumv|' + pair_id)` and the first n are taken (seed 49). The sample file and its sha are
written before the first call. Distorted is over-represented by design, so the agreement and kappa describe the label on
this sample; the summary rates come from the 390-pair population run, not from this sample.

## Models and calls

Haiku 5.5 labeller and Opus 5.5 reference, temperature 0, same prompt, one fact and one unit per call, two attempts per
call, as in `Relay-strict-fidelity-validation-v3-enriched.md`.

## Bars (same as the relay validation)

Passes if, for distorted-vs-not, agreement >= .80 **and** kappa >= .60, with 95% instance-cluster bootstrap intervals
(2,000 draws, seed 43). If the kappa CI lower bound is below .40 the label is wide-interval and the summary figures are
removed.

## Outcome

- **Passes**: the summary strict distortion (57/340) and omission (50/390) figures from `20261115_summary_rescore/rates.json`
  may be cited with Wilson 95% intervals, next to the relay figures under the same label.
- **Fails, or cannot run within the cap**: the summary strict and omission figures are removed from the response; the
  redundancy and relay results stay.
