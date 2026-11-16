# Amendment 1 to Per-fact-presence-points-v1

2026-11-15, written and hashed before any call under the amended design. Nothing else in the rule changes.

## Change

The **reference model** is Gemini 3.6 Flash (`google/gemini-3.6-flash`) instead of Opus 5.5. The labeller
stays Claude Haiku 5.5. The prompt, the atom definition, the statuses, the roll-up, the population (seed 47,
21 instances, 2,755 atoms), the bars, the CI method, the wide-interval rule and the $3.5 cap are unchanged.

## Reasons

1. **Cost.** Opus 5.5 is a reasoning-mandatory endpoint at the provider used here ("Reasoning is mandatory
   for this endpoint and cannot be disabled"). A completed 30-atom call measured 1,618 completion tokens at
   $0.0402; the full 155-call reference side projects to about $4.5 against a $3.5 cap. Gemini 3.6 Flash was
   the reference for prompt v3 and v4 and projects to about $1.0 for the same calls.
2. **Model policy.** The project rule is that expensive models such as Opus 5.5 are for small validation runs
   only, with the lead asked before a large one (the project's working rules; the same line is in
   the project status notes). This run is 310 calls, so Opus is outside the rule.

## Integrity

- Rule `Per-fact-presence-points-v1.md` sha256 `e6263584…`, prompt `per_fact_points_prompt_v1.json` sha256
  `86d84ff6…`, population `population.json` sha256 `1d1fd1af…` — all unchanged.
- The partial Opus run's records stay in `calls.jsonl`: 4 Haiku results and 2 Opus results, $0.121838. None of
  their labels is read or scored; the amended run uses separate call keys.
- Gemini remains a stronger reference than the Haiku labeller, so the cross-model agreement test is the same
  test; only the reference model changes.