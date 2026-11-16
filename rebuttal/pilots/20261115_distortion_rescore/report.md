# A4 — strict fidelity on the four additional models, re-scored under a validated label

2026-11-15. Rule `Strict-fidelity-new-models-v1.md` (sha `167dcb36…`), prompt `strict_fidelity_pair_prompt_v1.json`
(sha `182e7f9f…`), population `population_pairs.json` (sha `6d3bf2e3…`), validation sample (sha `bda4ab5d…`).
Haiku 5.5 labeller, Opus 5.5 reference, cap $4. Spend **$1.725887** (validation $1.438646 + full $0.287241).
Source of the replaced rates: `results/distortion_new_models/distortion_results.json` (Qwen-235B judge, unvalidated).

## Validation passed and is registered

120 pairs (30 per model, 41 instances), distorted vs not: agreement **.992 [.973, 1.000]**, κ **.937 [.796, 1.000]**.
Three-class agreement .975; the only three-class disagreements are 1 partial↔absent and 1 partial↔distorted.
Registered as `strict_fidelity_new_models_pairs` v1. Wide-interval rule does not apply.

## Result

| Model | Old strict | New strict (95% CI) | Old broad | New broad (95% CI) | faithful / partial / distorted / absent |
|---|---:|---|---:|---|---:|
| Gemini-FL | 1.3% (378) | **3.4% [1.8, 5.8]** (380) | 15.6% | 13.9% [10.6, 17.8] | 327 / 40 / 13 / 8 |
| GPT-4o-mini | 4.6% (349) | **9.2% [6.4, 12.7]** (348) | 22.6% | 14.1% [10.6, 18.2] | 299 / 17 / 32 / 12 |
| DeepSeek-R1-32B | 10.6% (123) | **5.8% [2.4, 11.6]** (121) | 43.9% | 52.9% [43.6, 62.0] | 57 / 57 / 7 / 99 |
| Gemma-4-31B | 0.8% (356) | **5.4% [3.3, 8.2]** (355) | 19.4% | 13.8% [10.4, 17.8] | 306 / 30 / 19 / 5 |

Strict = distorted / covered; broad = (distorted + partial) / covered; Clopper-Pearson 95% intervals.
Covered = eligible pairs labelled faithful, partial or distorted; absent pairs are listed, not in the denominator.

Cross-check on coverage: the new label calls 8 / 12 / 99 / 5 pairs absent, and the Qwen judge returned NO_MATCH on
10 / 11 / 97 / 4 of the same eligible pairs. The two coverage definitions agree within 1–2 pairs per model, so the
denominators are comparable (380 vs 378, 348 vs 349, 121 vs 123, 355 vs 356).

## Cause of the change

The change is not in which pairs are covered but in how covered pairs are classified. Qwen's class counts and the
validated label's differ mainly in **PARTIAL**. Qwen's PARTIAL on the same pairs is 54 / 63 / 66 / 41; the validated
label finds 40 / 17 / 30 / 57. The pairs Qwen called PARTIAL split both ways: for GPT-4o-mini, 29 of 63 become
faithful and 16 become distorted; for Gemma, 19 of 66 and 16; for Gemini-FL, about 6 of 54 and 8. So the broad rate
falls for three models while the strict rate rises. DeepSeek moves the other way: faithful 69 → 57 and distorted
13 → 7, both absorbed into PARTIAL (41 → 57).

Caveat on evidence: `distortion_results.json` stores counts only — the old runner drops the per-pair `records` before
saving (`scripts/run_distortion_new_models.py:208`) — so this cause is read from the class counts, not from
pair-by-pair disagreements. Reproducing the per-pair Qwen label would need a re-run of the Qwen judge (not done).

## Consequence

Under a validated label the published column understates strict distortion for the three models that rarely distort
(Gemini-FL ×2.6, GPT-4o-mini ×2.0, Gemma ×6.8) and halves DeepSeek's. The ordering changes: old — DeepSeek,
GPT-4o-mini, Gemini-FL, Gemma; new — GPT-4o-mini, DeepSeek, Gemma, Gemini-FL. On the broad rate, which is the more
stable quantity across labels, the old ordering survives except that GPT-4o-mini and Gemma swap and the three
non-DeepSeek models collapse into a 13.8–14.1% band. The paper cannot claim that added models rarely distort; it can
claim they contradict the gold shard on 1 in 11–30 covered pairs and leave it partial on another 1 in 10–21, while
DeepSeek leaves nearly half its covered pairs partial.

## Scoring fix

The first scoring pass added distorted pairs twice (the per-class increment and the covered-count block both
incremented `distorted`), which reported rates exactly two times the correct value. Fixed in
`scripts/distortion_rescore_run.py` (the covered block now only increments `covered`); `rates.json` re-written from
the same logged labels, no new calls. Counts now verify: faithful + partial + distorted = covered, and covered +
absent = eligible for every model.

## Ledger

$88.222614 before this step + $1.725887 = **$89.948501**. Calls in `calls.jsonl`, logs `validate.log`, `full.log`;
per-model rates in `rates.json`, validation record in `validation.json`.