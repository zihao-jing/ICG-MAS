# Relay strict-fidelity validation v2 (clarified prompt)

2026-11-15. Supersedes the v1 rule (`Relay-strict-fidelity-validation-v1.md`, sha `3d7b9258…`), which failed on
the Qwen relay population at kappa 0 (see `rebuttal/pilots/20261115_relay_validation/report.md`).

## Change

Same label, same models, same bars. One prompt clarification, `strict_fidelity_pair_prompt_v2.json`:
compressed restatements (including / ellipsis / ID ranges) that elide asserted members are **partial**; a
stated value, digit or ID set that differs from the fact is **distorted**, not partial. The cause read from the
five v1 disagreements is exactly this: Haiku accepted compressed numeric records as faithful and called a
mistyped digit partial.

Everything else is unchanged: Haiku 5.5 labeller, Opus 5.5 reference, one fact and one transmitted unit per
call, temperature 0, the same scoring quantity (distorted vs not, instance-cluster bootstrap, seed 43, 2,000
draws).

## Sample

30 fresh relay pairs from the same frozen population (`20261115_relay_rescore/population_pairs.json`), 10 per
protocol, drawn with **seed 48** by sorting on `sha256('48|relayval|' + pair_id)`. Pairs used in v1 are not
excluded by pair id (the seed changes the draw); overlap is reported in the build manifest.

## Bars

Register `strict_fidelity_relay_qwen` under prompt v2 only if agreement >= .80 **and** kappa >= .60 on
distorted-vs-not. If kappa's CI lower bound < .40 the label is wide-interval and kept out of the headline.
If it fails again, stop and diagnose; no further resample without approval.

## Cap and call budget

Cap **$0.5**. Estimated 30 Opus + 30 Haiku calls at the v1 measured rates (~$0.012 per pair) = about $0.37.
Every call logged to `calls.jsonl` with intent and result records.