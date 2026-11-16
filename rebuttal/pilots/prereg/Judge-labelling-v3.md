**SUPERSEDED by `Judge-labelling-v4.md` (2026-11-08). Historical record; original SHA-256 of the unmarked text `f9c860c27cfecf4ba86821826b8d6e4e72a8cf87d0042de867b47fdee3a2cfd1`.**

# Judge labelling v3: Gemini 3.6 Flash judges E2; derived eligibility rule; judge-quality measures; Mistral-S cross-check with a pre-registered backfire protocol (planning default, authors confirming)

2026-11-08. Supersedes `Judge-labelling-v2.md` (original SHA-256 `fc88d3f5b93aef7a990119bf83eafd1e96fee3541b8ab35bbe10412e28a5902d`; that file now carries a superseded line). v3 adds the eligibility rule, two judge-quality measures and the Mistral-S protection protocol; judges, frozen prompts, circularity table and Mistral-S scope are unchanged from v2. Nothing here has run (no full-run judge call).

## Judges

| Task | Judge | Cross-check |
|---|---|---|
| E1 fact labelling (80 held-out × 3 base models) | `google/gemini-3.6-flash` | none (30-instance author anchor, `E1-v7.md`) |
| E2 wave 1 base screening | `google/gemini-3.6-flash` | `mistralai/mistral-small-2603` |
| E2 wave 2 post-injection check | `google/gemini-3.6-flash` | `mistralai/mistral-small-2603` |
| E2 Part B natural-failure labels | `google/gemini-3.6-flash` | `mistralai/mistral-small-2603` |

**Frozen prompts:** `rebuttal/judge/judge_prompts_v2.json`, file SHA-256 `1aa908b77b9411bb20358bac2a7afab7b730c6431a9a2e45ee4968a2a85c358d`, prompts hash `e89cd06cd6bbe12740959be072422ff2df42304726aa00ce5b0420377a6c5098`. The prompt text is identical for Gemini and Mistral-S, and identical to the superseded v1 (`system_sha256` values unchanged); only the E2 `judge_model` field differs from v1. The model actually used is set in `rebuttal/pilots/configs/Judge-pilot-v2.json` (`allow_run: false`). The superseded v1 file is archived in `rebuttal/judge/archive/`.

**Dropped:** `qwen/qwen3.6-flash` (same family as the Qwen-235B matcher).

## Headline and labelling of rows

The E2 headline is the **Qwen-backbone comparison**. Every Gemini-backbone row in every E2 table carries the label **"same model as judge"**. Claim wording: Part A "judge-verified (Gemini 3.6 Flash), with author spot-checks and a Mistral-S cross-check"; Part B "closer to an LLM judge's labels" (the judge is independent of the Qwen-backbone rows only).

## Mistral-S cross-check (pre-registered; scope decided by the lead, 2026-11-08)

`mistralai/mistral-small-2603` **re-judges every E2 item**, with the same frozen prompts. This covers all items behind the Gemini-backbone rows and every item behind the Qwen-backbone rows, because both backbones run on the same items.

**Documented fallback, only if the check has to be cut (cost or schema failures):** re-judge all items behind the Gemini-backbone rows plus a Qwen-backbone slice: within each fault type, the first 30% of items in ascending SHA-256 of ["E2-mistral-slice-v1", 42, fault_type, item_key] (item_key as tie-break), at least 10 per type (all, if a type has fewer than 10). Any cut and its reason are reported.

**Reported for each row group:** Gemini–Mistral agreement as Cohen κ and percent agreement, with CIs. **If the E2 conclusion (which method is closer, or whether the audit names the stage and type more often) changes under Mistral's labels, the report says so plainly,** and the conclusion is stated as depending on the judge.

## Eligibility rule (derived in code; the judge's own `eligible` field is not used)

A candidate (base trace, target agent, fault type) is **eligible** if and only if the judge's `defect_free` is `yes` for the base trace **and every target check for that candidate passes**. For a candidate, the target check passes if the judge's entry for that agent has `in_every_sufficient_set = yes`, `carrier_outside_agent = no` and the candidate's fault type is in `feasible_fault_types`; an aggregation candidate has one target check per base trace. The rule is applied by `scripts` code to the judge's stored JSON. The judge prompts are unchanged.

## Judge-quality measures (pre-registered for the results)

1. **Disagreement of the judge's own `eligible` field with the rule.** For wave-1 outputs, the share where `eligible = yes` differs from the base-level reading of the rule: `defect_free = yes` and every target check in the output passes (primary reading), and, as a second figure, `defect_free = yes` and at least one target check passes. Per judge.
2. **Self-contradiction rate**: outputs with internally inconsistent fields, reported **per task, per wave and per judge**, with counts and exact 95% CIs. Fixed definitions: wave 1: `eligible = yes` with `defect_free != yes`; `defect_free = yes` with `any_partial_or_distorted_carrier = yes`. Part B: `class = single` with other than one listed defect; `class = multiple` with fewer than two. Wave 2: `exactly_one_critical_defect = yes` with `other_critical_facts_unchanged = no`. E1: `binary_call = reached_but_unused` while a board carrier of a fact in the first sufficient set is `absent` or `distorted`.

## Judges against the authors, and what Mistral-S can and cannot show (pre-registered)

- When the 20 author spot-check labels return, Gemini and Mistral-S are each measured **separately against the authors** on `defect_free` and on the target checks: agreement and Cohen κ with n and 95% CIs, per wave.
- If Mistral-S is clearly weak against the authors (agreement no better than chance, or clearly below Gemini's), the cross-check is reported as **limited**, and the judge's credibility rests on author agreement. **The agreement between the two judges is never presented as evidence about Gemini**, in either direction.
- The author check covers **screening only** (waves 1 and 2). **Part B labels have no human check**; Part B is described as "closer to an LLM judge's labels" and both judges' labels are reported.
- *Basis (reserved pilot items, n = 13 decision pairs, descriptive only):* pooled Gemini–Mistral agreement was 8 of 13 (61.5%, exact 95% CI 32–86%), the same as the 61.5% expected by chance (κ = 0.0). At that level the cross-check cannot support a claim of judge independence. What is reported instead: Gemini against authors, the judges' self-contradiction rates, the eligibility-field disagreement, and a **robustness statement** ("does the E2 conclusion survive under Mistral's labels?"), not an agreement claim.

## Circularity table

| Judging task | Judge | Models evaluated or compared against | Shared model? |
|---|---|---|---|
| E1 labels (reference for the Qwen-235B matcher) | Gemini 3.6 Flash | Matcher Qwen-235B; traces from Qwen-235B, GPT-4o-mini, Gemma-4-31B | The judge is not evaluated. Downstream, E1 labels route E4 repairs and pick the E2-C casebook, which use Gemini as the stronger repair arm and a baseline backbone. The author anchor checks the judge directly. |
| E2 wave 1, wave 2, Part B, **Qwen-backbone rows** (headline) | Gemini 3.6 Flash | [R1], Who&When, MAST and our audit with the Qwen-235B backbone; traces from Qwen-235B, GPT-4o-mini, Gemma | **No.** (Qwen-235B is also the matcher; the judge is a different model.) |
| E2 wave 1, wave 2, Part B, **Gemini-backbone rows** | Gemini 3.6 Flash | The same methods with the Gemini backbone | **Yes: the judge and the backbone are the same model.** These rows are labelled "same model as judge"; a method that shares the judge's biases may score closer to its labels. |
| E2 cross-check | Mistral-S | Same items and rows | No shared model: Mistral-S has no role in any new experiment. |

## Cost (Gemini and Mistral prices, 2026-11-08 snapshot)

Planned basis: about 4,500 input and 6,000 output tokens per call. **Measured on reserved pilot items** (31 calls, 0 failed, $0.151 in total): Gemini $0.0079 per item for E1, $0.0107 for wave 1, $0.0067 for wave 2, $0.0061 for Part B; Mistral-S $0.0005–0.0007 per item. Extrapolated to the full runs: E1 240 calls $1.89; wave 1 68 calls $0.73; wave 2 up to 200 calls $1.34; Part B about 126 calls $0.77 (batch 2); Mistral-S on the same items about $0.24 in total (wave 1 $0.05, wave 2 $0.14, Part B $0.06). Wave 2 was measured on only 3 items.
