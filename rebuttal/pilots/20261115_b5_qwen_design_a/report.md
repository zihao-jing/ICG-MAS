# B5 checks: Qwen audit through the design-A pipeline

2026-11-15. Design-A pipeline exactly: frozen Qwen facts, the same `CARRIER_PROMPT`, the same
`diagnose_with_sharding`, the same 89 cases. Cap $1.00, spend **$0.163918** (89 Qwen carrier calls + 6 Gemini retry calls, three attempts on each of the two failed cases).
No rule change; nothing here is a new method.

## Corrected 2x2

Facts are Qwen-generated in every cell, as in design A. Carrier labeller and judge swap:

| cell | injected (n=30) | cohort (n=59) | all (n=89) |
| --- | ---: | ---: | ---: |
| audit, Gemini carrier labeller (design A) | 21 | 40 | **61** |
| audit, Qwen carrier labeller (this run) | 27 | 30 | **57** |
| judge, Gemini 3.6 Flash | 24 | 43 | **67** |
| judge, Qwen-235B | 27 | 29 | **56** |

The earlier 70/89 audit-Qwen row is not this pipeline. It came from diagnosing the stored Stage-2 matcher
records (`score_a` reads `EARLIER_AUDIT`), where the fact-to-checkpoint alignment was already fixed; the
design-A pipeline re-labels the frozen Qwen facts through `carrier_step` and arrives at 57. The 70 row stays
on record labelled "earlier pipeline", not as a design-A cell.

**Reading.** With the pipeline held fixed, the backbone gap is +6 for the judge on Gemini and +1 for the audit
on Qwen — the signs disagree and neither reaches 6 points. The audit is not uniformly ahead; the earlier
Qwen advantage (+14 over the Qwen judge) was an artefact of comparing pipelines.

## Sharding decision path, per cell

Both cells call the same `diagnose_with_sharding` on the same frozen facts; the only difference is which model
labels the carriers. The path is identical in both cells: a fact whose extraction list is empty gives
`extraction_omission`; that label is then re-attributed to `sharding` when the frozen lexical rule
(`content_recall` at the 0.8/0.4 thresholds over the source shards) finds it absent from the agent's input.
Neither cell is advantaged relative to the other by construction. Both are, however, consistent with the
cohort truth by construction: the cohort's extraction/sharding split was assigned by that same rule, so
cohort accuracy on the sharding side is a consistency check for both cells, not independent accuracy.

Cohort split, stated separately:

| cohort truth | n | Gemini cell names it | Qwen cell names it |
| --- | ---: | ---: | ---: |
| sharding | 20 | 5 | 3 |
| extraction | 39 | 35 | 27 |

## Why the cells disagree (29 cases)

Two cases have no Gemini carrier record: `inj/gpt4omini/4hop1__93963_170667_443779_52195` and
`inj/gemma31b/4hop1__151903_5274_458768_33677`. Both retries failed again on the deterministic prompt; they
are **missing** in the Gemini cell, not wrong, and are excluded from the comparison (`stage = None`).

The other 27 all differ in one way: whether at least one fact's extraction carrier list is empty. In 24 of 27,
Qwen's carrier labeller returns fewer facts missing from the extraction pool than Gemini's; Gemini returns
more in 2 (`coh/gemma31b/3hop1__506062_792411_51423`, `coh/qwen235b/4hop1__473563_309800_355213_203322`), and 1
is tied (`coh/gpt4omini/4hop1__28352_53706_795904_580996`). Board-only differences: none. The direction is systematic — Qwen's carrier
labels call a fact present at extraction where Gemini's call it absent — so Qwen's cell reaches
`extraction_omission` less often (and therefore the sharding re-attribution less often), and lands on
transmission or aggregation instead. Representative rows:

| case | known | Gemini | Qwen | facts empty at extraction, Gemini vs Qwen |
| --- | --- | --- | --- | --- |
| `coh/gemma31b/4hop1__3496_5274_458768_33637` | extraction | extraction | transmission | 6/7 vs 0/7 |
| `coh/gemma31b/4hop2__9988_158985_70784_61381` | extraction | extraction | transmission | 2/5 vs 0/5 |
| `coh/gpt4omini/3hop1__702699_792411_51423` | sharding | extraction | transmission | 2/5 vs 0/5 |
| `inj/qwen235b/3hop1__144439_443779_52195` | transmission | extraction | transmission | 2/8 vs 0/8 |

The full 29-row table is in `disagreements.md`.

## Qwen judge's cohort misses (30 of 59)

| truth \ Qwen judge | extraction | sharding | aggregation |
| --- | ---: | ---: | ---: |
| extraction (39) | 19 | 16 | 4 |
| sharding (20) | 9 | 10 | 1 |

16 of the 30 misses are extraction traces the Qwen judge calls sharding, and 9 are the reverse. The judge
does not use the lexical shard rule, so its extraction/sharding boundary is its own reading of the trace, and
it splits these two classes differently from the frozen rule in both directions. Its injected accuracy
(27/30) is unaffected by this boundary.

## Gaps and the fix

The remaining gap between the audit cells is a carrier-labelling threshold difference on the same facts, not a
pipeline or population difference. The fix that removes it is the one already in the design: hold the labeller
fixed across arms (design A) and report the carrier-labeller swap as the measured effect; do not compare an
audit row scored on stored matcher records against a judge row scored from scratch.

## Ledger

$0.163918 this run (95 calls: 89 Qwen carriers + 6 Gemini retry attempts).

## Transport

No CLI route used. All calls through OpenRouter, model strings as logged.