# Validating the strict-fidelity label on the Qwen relay population: rule v1

2026-11-15, frozen and hashed before any call. The relay rates in `20261115_relay_rescore/` were produced by
the label registered for the four-model pairs (`strict_fidelity_new_models_pairs`). That registration covers
the label and the prompt, not this population, so this run validates it on the relay pairs themselves.

## Population and sample

- Population: the 945 Qwen-235B relay pairs (`20261115_relay_rescore/population_pairs.json`, sha
  `3dfe8ac3…`), three protocols x 315.
- Sample: **10 pairs per protocol** (30 total), ordered by `sha256('47|relayval|' + pair_id)` within each
  protocol. The sample file and its sha are written before any call.
- The sample is drawn at random within protocol, not stratified by the old Qwen judge's label: that label is
  unvalidated and must not shape the validation set.

## Label

- Identical to step 9: prompt `strict_fidelity_pair_prompt_v1.json` (sha `182e7f9f…`), the v10 strict-fidelity
  system text, one fact (the agent's gold shard) and one entry (the transmitted unit) per call, question not
  shown, gold and unit truncated at 2000 characters, temperature 0.
- Labeller Claude Haiku 5.5; reference Opus 5.5 (reasoning is mandatory at this endpoint and is billed).
- Classes: faithful / partial / distorted / absent, as the prompt defines them.

## Bars and registration

- Agreement and Cohen's kappa on **distorted vs not** (the quantity the relay rate uses), each with a 95% CI
  (instance-cluster bootstrap, 2,000 draws, seed 43); three-class agreement beside them.
- Bars: agreement >= .80 and kappa >= .60. Wide-interval rule: kappa CI lower < .40 means not headline.
- Register as `strict_fidelity_relay_qwen` v1 in `rebuttal/validations/registry.json` only if both bars pass.
  Only then may the text quote the validated relay rates; until then they are an unvalidated re-score.
- If the bars fail, stop the text use of the relay rates, read the disagreements, and report the cause.

## Cap and logging

Cap **$0.5** for the 30 reference and 30 labeller calls; every call logged; stop if the running projection
would exceed the cap. No prompt tuning on the sample.