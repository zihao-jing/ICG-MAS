**SUPERSEDED by `Judge-labelling-v5.md` (2026-11-08). Historical record; original SHA-256 of the unmarked text `5793486b7940f12488a9be27bdb6b6e74e2b56f3920707afbe6576567d12aaaf`.**

# Judge labelling v4: Gemini 3.6 Flash is the only judge; derived eligibility rule; judge-quality measures; a pre-registered pilot of GPT-4o-mini as a possible cross-check (planning default, authors confirming)

2026-11-08. Supersedes `Judge-labelling-v3.md` (original SHA-256 `f9c860c27cfecf4ba86821826b8d6e4e72a8cf87d0042de867b47fdee3a2cfd1`; that file now carries a superseded line). v4 removes the earlier second cross-check model from the design entirely, refreezes the prompts file with metadata only (prompt text and prompts hash unchanged), and pre-registers a pilot of a different cross-check candidate, with its decision rule and both outcomes, **before** that pilot runs. Nothing here has run at full scale: no full-run judge call.

## Judges

| Task | Judge (exact ID) | Frozen prompt |
|---|---|---|
| E1 fact labelling (80 held-out × 3 base models) | `google/gemini-3.6-flash` | `E1_fact_labelling` |
| E2 Part A wave 1: base screening | `google/gemini-3.6-flash` | `E2_wave1_base_screening` |
| E2 Part A wave 2: post-injection check | `google/gemini-3.6-flash` | `E2_wave2_post_injection` |
| E2 Part B: natural-failure labels | `google/gemini-3.6-flash` | `E2_partB_natural_failure` |

**Frozen prompts:** `rebuttal/judge/judge_prompts_v3.json`, file SHA-256 `3b4257a1de364511c062e565c5ae3e41759ab1a96b0594e153bae0d1646dc4e7`, prompts hash `e89cd06cd6bbe12740959be072422ff2df42304726aa00ce5b0420377a6c5098` (the same prompt text as the superseded earlier files, archived in `rebuttal/judge/archive/`). The model used is set in `rebuttal/pilots/configs/Judge-pilot-v3.json` (`allow_run: false`). temperature 0, seed 42; schema failures are logged and reported; no automatic retry. Judge output is always called a judge label. `qwen/qwen3.6-flash` was dropped (same family as the Qwen-235B matcher).

## Headline and labelling of rows

The E2 headline is the **Qwen-backbone comparison**. Every Gemini-backbone row carries the label **"same model as judge"**. Claim wording: Part A "judge-verified (Gemini 3.6 Flash), with author spot-checks"; Part B "closer to an LLM judge's labels", and every Part B table says in its reading: **"no human check of these labels"**.

## Eligibility rule (derived in code; the judge's own `eligible` field is not used)

A candidate (base trace, target agent, fault type) is **eligible** if and only if the judge's `defect_free` is `yes` for the base trace **and every target check for that candidate passes**. The target check passes if the judge's entry for that agent has `in_every_sufficient_set = yes`, `carrier_outside_agent = no` and the candidate's fault type is in `feasible_fault_types`; an aggregation candidate has one target check per base trace. Judge prompts are unchanged.

## Judge-quality measures (pre-registered for the results)

1. **Disagreement of the judge's own `eligible` field with the rule**, for wave-1 outputs: the share where `eligible = yes` differs from `defect_free = yes` and every target check passing (primary), and, as a second figure, `defect_free = yes` and at least one target check passing.
2. **Self-contradiction rate**: outputs with internally inconsistent fields, **per task, per wave**, with counts and exact 95% CIs. Fixed definitions: wave 1: `eligible = yes` with `defect_free != yes`; `defect_free = yes` with `any_partial_or_distorted_carrier = yes`. Part B: `class = single` with other than one listed defect; `class = multiple` with fewer than two. Wave 2: `exactly_one_critical_defect = yes` with `other_critical_facts_unchanged = no`. E1: `binary_call = reached_but_unused` while a board carrier of a fact in the first sufficient set is `absent` or `distorted`.

## What the author check covers

When the 20 author spot-check labels return, Gemini is measured against them on `defect_free` and the target checks: agreement and Cohen κ with n and 95% CIs, per wave. The author check covers **screening only** (waves 1 and 2). **Part B labels have no human check** (a small author spot-check of Part B is a costed batch-2 proposal, not part of this design). The judge's credibility rests on author agreement plus the two judge-quality measures above.

## Cross-check candidate: GPT-4o-mini pilot (decision rule fixed before the run)

**Why a candidate.** There is no cross-check in the default design. A second model could only help if it discriminates. A pilot decides whether to propose it.

**Pilot.** Model `openai/gpt-4o-mini`, the frozen prompts above, on 5 reserved items that GPT-4o-mini did not generate: wave 1 on `2hop__466700_214359` and `2hop__809096_491515`; wave 2 on `2hop__466700_214359:extraction_omission` and `2hop__809096_491515:distortion`; Part B on `2hop__24661_81961`. Reserved pilot items only; no evaluation ID. It is a single call per item with no retry.

**"Discriminates" means all four of these hold:**
1. every output is format-valid (all required fields present and parseable);
2. it answers **"no" at least once on wave 2** (in any of the four wave-2 fields, over the two wave-2 items);
3. **none of its answers is impossible**: in particular `one_visible_step_changed_if_aggregation = yes` on an evidence edit (extraction omission, selection omission or distortion) is impossible;
4. **no self-contradictions** by the definitions above.

**Report:** result against these four conditions, raw outputs, tokens and cost, and its agreement with Gemini on the pilot items with n stated (n = 5 decision pairs: wave-1 `defect_free` 2, wave-2 `exactly_one_critical_defect` 2, Part B `class` 1; descriptive only).

**Pre-registered outcomes (either result is fixed in advance):**
- **If it discriminates:** it is brought to the lead as a *proposed* cross-check under "Settings changes for approval". It is **not** switched on by the worker, and the design does not change until the lead approves.
- **If it does not discriminate:** **E2 has no cross-check.** The judge's credibility rests on the 20 author spot-checks plus the judge-quality rates (own-field disagreement and self-contradiction). No other model is tried.

## Circularity table

| Judging task | Judge | Models evaluated or compared against | Shared model? |
|---|---|---|---|
| E1 labels (reference for the Qwen-235B matcher) | Gemini 3.6 Flash | Matcher Qwen-235B; traces from Qwen-235B, GPT-4o-mini, Gemma-4-31B | The judge is not evaluated. Downstream, E1 labels route E4 repairs and pick the E2-C casebook, which use Gemini as the stronger repair arm and a baseline backbone. The author anchor checks the judge directly. |
| E2 wave 1, wave 2, Part B: **Qwen-backbone rows** (headline) | Gemini 3.6 Flash | [R1], Who&When, MAST and our audit with the Qwen-235B backbone | **No** |
| E2 wave 1, wave 2, Part B: **Gemini-backbone rows** | Gemini 3.6 Flash | The same methods with the Gemini backbone | **Yes: same model as judge.** These rows carry that label. |

## Cost (2026-11-08 snapshot)

Measured on reserved pilot items (Gemini calls, 0 failed): $0.0079 per item for E1, $0.0107 for wave 1, $0.0061 for Part B and $0.0067 for wave 2. **The wave-2 figure rests on 3 items.** Extrapolated to the full runs: E1 240 calls $1.89; wave 1 68 calls $0.73; wave 2 up to 200 calls $1.34; Part B about 126 calls $0.77 (batch 2).
