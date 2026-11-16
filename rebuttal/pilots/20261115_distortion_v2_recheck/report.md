# Four-model strict fidelity under the clarified prompt (9f)

2026-11-15. Rule `Strict-fidelity-v2-recheck.md` (sha `97c48f96...`), prompt `strict_fidelity_pair_prompt_v2.json` (sha `fc725839...`). 1328 board pairs re-labelled with Haiku 5.5; reference labels are the existing Opus 5.5 labels on the 120-pair validation set (no new Opus calls). Spend **$0.525472**, cap $0.5.

## Validation of the v2 prompt on this population

| quantity | value [95% CI] |
| --- | --- |
| distorted vs not, agreement | 0.975 [0.943, 1.000] |
| distorted vs not, kappa | 0.844 [0.392, 1.000] |
| three-class agreement | 0.967 |

Bars agreement >= .80, kappa >= .60: **PASSES**.

| reference \ labeller | faithful | partial | distorted | absent |
| --- | ---: | ---: | ---: | ---: |
| faithful | 86 | 1 | 0 | 0 |
| partial | 0 | 8 | 1 | 0 |
| distorted | 0 | 0 | 9 | 0 |
| absent | 0 | 0 | 2 | 13 |

## Rates under the v2 prompt

| model | covered | faithful | partial | distorted | absent | strict [95% CI] | broad [95% CI] |
| --- | ---: | ---: | ---: | ---: | ---: | --- | --- |
| geminifl | 382 | 323 | 39 | 20 | 6 | 5.2% [3.2, 8.0] | 15.4% [12.0, 19.5] |
| gpt4omini | 350 | 298 | 17 | 35 | 10 | 10.0% [7.1, 13.6] | 14.9% [11.3, 19.0] |
| deepseekr1_32b | 133 | 53 | 56 | 24 | 87 | 18.0% [11.9, 25.6] | 60.2% [51.3, 68.5] |
| gemma31b | 356 | 303 | 31 | 22 | 4 | 6.2% [3.9, 9.2] | 14.9% [11.4, 19.0] |

Strict = distorted / covered; broad = (distorted + partial) / covered.

## Registration

Registered as `strict_fidelity_new_models_pairs_v2` (prompt v2).

## Ledger
Spend $0.525472.

## Cap breach and top-up

The population label was capped at $0.5. The parallel relabel finished at **$0.503568, a breach of
$0.003568**, because eight calls were in flight when the last cap check fired — the same in-flight effect seen
on the chunked runs, here on a single cap. **53 of the 1,328 pairs were skipped** at that cap.

The 53 skipped pairs were then labelled under a separate approved cap of **$0.05**, applied to that invocation
only (`--fresh-cap`); they cost **$0.021904**, inside the cap. All **1,328 pairs** now carry a v2 label, and the
rates above are on the full population. The run total is **$0.525472** ($0.503568 + $0.021904).

## Validation sample, reconciled

The first pass validated on **119 of the 120** reference pairs because one reference pair was among the 53
skipped at the cap. After the top-up it validates on **120 of 120**. The numbers are essentially unchanged
(agreement .975 [.943, 1.000], kappa .844 [.392, 1.000]; the extra pair agrees), so the table above is the
reconciled one and the earlier 119 figure is superseded.

## Like-for-like comparison (both prompts, same 1,328 pairs)

`scripts/distortion_v2_compare.py`, no calls.

| model | n | v1 strict | v2 strict [95% CI] | v1 broad | v2 broad |
| --- | ---: | --- | --- | ---: | ---: |
| Gemini-FL | 388 | 3.4% | **5.2% [3.2, 8.0]** | 13.9% | 15.4% |
| GPT-4o-mini | 360 | 9.2% | **10.0% [7.1, 13.6]** | 14.1% | 14.9% |
| DeepSeek-R1-32B | 220 | 5.8% | **18.0% [11.9, 25.6]** | 52.9% | 60.2% |
| Gemma-4-31B | 360 | 5.4% | **6.2% [3.9, 9.2]** | 13.8% | 14.9% |

With the full population the v1 numbers return to the published values (Gemma back to 5.4% on 356 covered
pairs); the v2 rates move up on all four models and most on DeepSeek.

## Wide-interval

The kappa interval is [0.392, 1.000]: its lower bound sits just under .40, so under the standing rule the
label is **marked wide-interval and kept out of the headline**, even though both point estimates clear the bars.

## Limitation on the DeepSeek row

DeepSeek moves most (5.8% -> 18.0%). Under v2 its absent count falls (99 -> 87) and its distorted count rises
(7 -> 24): pairs the v1 prompt called partial or absent on a compressed numeric record are now called distorted
because the stated values differ. That is the rule change working as written, but with 220 pairs and a kappa CI
that reaches .39 it is the row most sensitive to the label; do not headline the 18% without saying which prompt
produced it.
