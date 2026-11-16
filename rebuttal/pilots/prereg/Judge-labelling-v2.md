**SUPERSEDED by `Judge-labelling-v3.md` (2026-11-08). Historical record; original SHA-256 of the unmarked text `fc88d3f5b93aef7a990119bf83eafd1e96fee3541b8ab35bbe10412e28a5902d`.**

# Judge labelling v2: Gemini 3.6 Flash judges E2; Mistral-S cross-checks (planning default, authors confirming)

2026-11-08. Supersedes `Judge-labelling-v1-archived.md`. **Revised 2026-11-08 before any run** (previous hash `cf6d00d3dcc84009f31c98d1a4f487c57240a40993584a5c12914fd5ef535993`): Ring-1T removed, prompts refrozen as v2, Mistral-S scope decided. Nothing here has run: no judge call, no pilot. Paper models only (exact IDs).

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

## Circularity table

| Judging task | Judge | Models evaluated or compared against | Shared model? |
|---|---|---|---|
| E1 labels (reference for the Qwen-235B matcher) | Gemini 3.6 Flash | Matcher Qwen-235B; traces from Qwen-235B, GPT-4o-mini, Gemma-4-31B | The judge is not evaluated. Downstream, E1 labels route E4 repairs and pick the E2-C casebook, which use Gemini as the stronger repair arm and a baseline backbone. The author anchor checks the judge directly. |
| E2 wave 1, wave 2, Part B, **Qwen-backbone rows** (headline) | Gemini 3.6 Flash | [R1], Who&When, MAST and our audit with the Qwen-235B backbone; traces from Qwen-235B, GPT-4o-mini, Gemma | **No.** (Qwen-235B is also the matcher; the judge is a different model.) |
| E2 wave 1, wave 2, Part B, **Gemini-backbone rows** | Gemini 3.6 Flash | The same methods with the Gemini backbone | **Yes: the judge and the backbone are the same model.** These rows are labelled "same model as judge"; a method that shares the judge's biases may score closer to its labels. |
| E2 cross-check | Mistral-S | Same items and rows | No shared model: Mistral-S has no role in any new experiment. |

## Cost (Gemini and Mistral prices, 2026-11-08 snapshot)

Planned basis: about 4,500 input and 6,000 output tokens per call (measured input on real reserved requests is lower, about 2,300–4,200 tokens; output is unmeasured until a pilot runs). Gemini 3.6 Flash $0.75 / $3.75 per million; Mistral-S $0.15 / $0.60 per million. E2 judge, Gemini: wave 1 68 + wave 2 up to 200 + Part B about 126 = 394 calls, **about $10.2, about $20.4 with a 2× margin** (batch 1: 268 calls, $6.94; Part B in batch 2: $3.26). Mistral cross-check: same call counts, about $1.68 in total (batch 1: $1.15). Measured cost: none yet; no judge call has run.
