**SUPERSEDED by `Judge-labelling-v2.md` (2026-11-08). Historical record only; do not follow.**

# Judge labelling v1: LLM judges replace human annotation (planning default, authors confirming)

2026-11-08. Nothing here has been run. No judge labelling, no pilot call. Models are the paper's exact IDs only.

## Judges

| Task | Judge (exact ID) | Frozen prompt |
|---|---|---|
| E1 fact labelling (80 held-out instances × 3 base models) | `google/gemini-3.6-flash` | `E1_fact_labelling` |
| E2 Part A wave 1: base screening | `inclusionai/ring-2.6-1t` | `E2_wave1_base_screening` |
| E2 Part A wave 2: post-injection check | `inclusionai/ring-2.6-1t` | `E2_wave2_post_injection` |
| E2 Part B: natural-failure labels | `inclusionai/ring-2.6-1t` | `E2_partB_natural_failure` |

Prompts are in `rebuttal/judge/judge_prompts_v1.json`: file SHA-256 `8b257aaf78cac6cd38380e2e543efb8677ac708289b72fe6ec13ebe75c61fa07`, prompts hash `e879635829dc8ddff198d31e4aea5b9f415852fb28e63e1ed93c0e74b14a649c`. The rubric is the existing author guideline for each task with human-workflow and statistics sentences removed; the judge sees only blind-view fields. temperature 0, seed 42. Schema failures are logged and reported; no automatic retry. Judge output is always called a judge label.

**Ring-1T availability (checked 2026-11-08):** `inclusionai/ring-2.6-1t` has a model page on OpenRouter but **zero endpoints** and is absent from the live model list (`pricing_snapshot.json`). It cannot currently be priced or called. The paper also reports low extraction success for Ring-1T (about 38% at n = 5, near zero at n = 10), a format-reliability risk for a judge. The E2 judge assignment is unresolved until the authors choose a route; see "Settings changes for approval".

## Circularity table

| Judging task | Judge | Models evaluated or compared against | Shared model? |
|---|---|---|---|
| E1 labels (the reference the Qwen matcher is scored against) | Gemini 3.6 Flash | The matcher is Qwen-235B; the traces come from Qwen-235B, GPT-4o-mini and Gemma-4-31B | The judge is not a model being evaluated. Downstream, E1 labels route E4 repairs and pick the E2-C casebook, and both use Gemini as the stronger-model arm or baseline backbone. In plain words: the same model that labels the facts is later used as one of the repairers and baselines. Author anchor labels check the judge directly. |
| E2 wave 1 and wave 2 (is the base clean, is one defect added) | Ring-1T | Base traces from Qwen, GPT-4o-mini, Gemma; methods scored later: [R1], Who&When, MAST and our audit with Qwen-235B and Gemini backbones | None shared. |
| E2 Part B (natural-failure reference) | Ring-1T | Same methods and backbones; traces from Qwen, GPT-4o-mini, Gemma | None shared. |

Ring-1T is the only paper model with no other role in the comparison.

## E2 Part A spot-check rule (fixed before any judge label exists)

- **Size and strata:** 20 traces: wave 1, 2 per fault type (8); wave 2, 3 per fault type (12); fault types are extraction omission, selection omission, distortion, aggregation. Wave 1 items are (base trace, fault type) judgements; wave 2 items are injected after-traces.
- **Pool:** judge-KEPT items only (items the judge marked defect-free for wave 1, or single-defect for wave 2), since those are the items that would enter the evaluation. Judge-rejected items are not spot-checked; the cost is that false rejections are not measured, which is stated in the report.
- **Order:** ascending SHA-256 of canonical JSON ["E2-spot-v1", 42, wave, fault_type, item_id], item_id as tie-break; take the first n per cell. A cell with fewer kept items than n contributes all of them, and the shortfall is reported; it is not redistributed.
- **Author assignment:** one author per trace, by position in the combined SHA order modulo 4 (A, B, C, D). Authors are blind to the judge's reasoning but see the same blind trace the judge saw.
- **Reported:** judge–author agreement on "defect-free" (wave 1) and "single defect" (wave 2), counts and exact Clopper–Pearson 95% CIs, per wave and pooled. **Any single author disagreement on "defect-free" or "single defect" drops that trace;** the number of disagreements is reported. No agreement threshold is set.
- **Hours:** at the packet's planning times (7 min per MuSiQue base pass, 5 min per post-check) the 20 spot-checks take 1.9 h in total; reserve 4 h (1 h per author) for a 2× margin.

## E2 Part B

The judge labels every Part B trace in full (single, multiple or indeterminate, with reference defects). The claim is "closer to an independent LLM judge's labels". There is no human reference for Part B and it is not described as one.

## Claim wording

- E2 Part A: "judge-verified, with N author spot-checks" (N = 20 planned).
- E2 Part B: "closer to an independent LLM judge's labels".
- E1: "validated against author labels on a 30-instance anchor; compared with an LLM judge's labels on 80 instances".
