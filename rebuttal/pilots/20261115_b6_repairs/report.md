# Audit-guided repairs on the 59 missing-fact cases

2026-11-15. Rule `B6-audit-guided-repairs.md` (sha `7609e35c...`), amendment 2 (sha `85b72762...`), amendment 3 (post-hoc sensitivity), amendment 4 (full-evidence routing), amendment 5 (verbatim quotation) and amendment 6 (bridge-aware extraction). One repair procedure, two targets: re-extraction from the flagged agent shard (extraction cases), re-routing the source support passage that carries the fact through the same extraction step (sharding cases). Original arm = the same trace's stored baseline. Spend $0.011524, cap $5.00.

| cell | cases | delivered | undelivered | correct: repaired / original | diff [95% CI] | F1: repaired / original | diff [95% CI] | gain / loss / tie |
| --- | ---: | ---: | ---: | --- | --- | --- | --- | --- |
| extraction | 39 | 18 | 21 | 12 / 0 | +0.308 [+0.179, +0.462] | 0.383 / 0.042 | +0.341 [+0.208, +0.488] | 12 / 0 / 27 |
| sharding | 20 | 0 | 20 | 0 / 0 | +0.000 [+0.000, +0.000] | 0.078 / 0.078 | +0.000 [+0.000, +0.000] | 0 / 0 / 20 |
| all | 59 | 18 | 41 | 12 / 0 | +0.203 [+0.119, +0.305] | 0.279 / 0.054 | +0.225 [+0.136, +0.328] | 12 / 0 / 47 |

Paired bootstrap over cases, 2,000 draws, seed 43. The table above is every case in the cell: an undelivered case is scored on its original answer, so it contributes a zero difference and stays in the denominator.

### Delivered cases only

| cell | delivered | correct: repaired / original | diff [95% CI] | F1: repaired / original | diff [95% CI] | gain / loss / tie |
| --- | ---: | --- | --- | --- | --- | --- |
| extraction | 18 | 12 / 0 | +0.667 [+0.444, +0.889] | 0.792 / 0.053 | +0.738 [+0.552, +0.907] | 12 / 0 / 6 |
| sharding | 0 | — | — | — | — | — |
| all | 18 | 12 / 0 | +0.667 [+0.444, +0.889] | 0.792 / 0.053 | +0.738 [+0.552, +0.907] | 12 / 0 / 6 |

This subset is conditional on the gate delivering; it is not the cell's average effect.

## Which sharding diagnoses a supplied passage can support

The flagged fact is stated in a supplied passage at the gate threshold (recall >= 0.8) in **6 of 20** sharding cases. The other **14 diagnoses are unsupported**: no passage the instance supplied states the fact, so no gold-free repair of the sharding stage can deliver it. The sharding diagnosis is restricted to the 6 supported cases.

| supported case | best passage recall | passage agent |
| --- | ---: | ---: |
| coh/gemma31b/2hop__304852_758385 | 1.00 | 1 |
| coh/gemma31b/2hop__342746_679190 | 1.00 | 0 |
| coh/gemma31b/2hop__128342_375952 | 0.90 | 1 |
| coh/gpt4omini/2hop__71294_494136 | 0.86 | 1 |
| coh/gemma31b/3hop1__454441_55349_651302 | 0.86 | 2 |
| coh/gemma31b/2hop__46213_494136 | 0.83 | 0 |

The corrected single-passage pass delivered none of these six: even where a passage states the fact, the extracted units paraphrase it below the 0.8 gate. The full-evidence arm delivered one case, `coh/gemma31b/2hop__554145_88622`, which is not one of the six and stayed incorrect.

## B6c: verbatim quotation on the six supported cases (amendment 5)

The extractor must copy sentences exactly; nothing else changes.

| cases | delivered | delivered 95% CI | undelivered | correct repaired / original | diff [95% CI] |
| ---: | ---: | --- | ---: | --- | --- |
| 6 | 0 | 0.000-0.459 | 6 | — | — |

Four of the six returned no usable quote: three refusals ("the provided text does not contain ...") and one "no sentences ... bear on the question". The other two quoted sentences that do not carry the fact. The extractor screened for sentences that mention the question's entities, so the bridge sentence the fact needs was not quoted.

| case | best passage recall | units | delivered | outcome |
| --- | ---: | ---: | ---: | --- |
| coh/gemma31b/2hop__128342_375952 | 0.90 | 1 | 0 | undelivered |
| coh/gemma31b/2hop__46213_494136 | 0.83 | 1 | 0 | undelivered |
| coh/gpt4omini/2hop__71294_494136 | 0.86 | 3 | 0 | undelivered |
| coh/gemma31b/2hop__304852_758385 | 1.00 | 1 | 0 | undelivered |
| coh/gemma31b/3hop1__454441_55349_651302 | 0.86 | 1 | 0 | undelivered |
| coh/gemma31b/2hop__342746_679190 | 1.00 | 1 | 0 | undelivered |

## B6d: bridge-aware extraction on the six supported cases (amendment 6)

Verbatim quotation with the entity screen removed: quote every sentence the chain needs, including bridge sentences.

| cases | delivered | delivered 95% CI | undelivered | correct repaired / original |
| ---: | ---: | --- | ---: | --- |
| 6 | 0 | 0.000-0.459 | 6 | — |

| case | best passage recall | units | delivered | outcome |
| --- | ---: | ---: | ---: | --- |
| coh/gemma31b/2hop__128342_375952 | 0.90 | 1 | 0 | undelivered |
| coh/gemma31b/2hop__46213_494136 | 0.83 | 1 | 0 | undelivered |
| coh/gpt4omini/2hop__71294_494136 | 0.86 | 5 | 0 | undelivered |
| coh/gemma31b/2hop__304852_758385 | 1.00 | 1 | 0 | undelivered |
| coh/gemma31b/3hop1__454441_55349_651302 | 0.86 | 1 | 0 | undelivered |
| coh/gemma31b/2hop__342746_679190 | 1.00 | 1 | 0 | undelivered |

**The sharding repair is closed as a negative result.** Across the corrected single-passage pass, full-evidence routing, verbatim quotation and bridge-aware quotation, no gold-free extraction delivers these six bridge facts under the frozen gate. The cause read from the outputs is the extractor's own behaviour: it screens sentences by question entities, refuses when a document does not mention them, and paraphrases or summarises what it does quote; it does not copy the bridge sentence even when the passage states the fact. This is an extractor limitation, not a passage or gate defect.

## No-unit control (delivered cases)

| cell | n | control correct | repaired - control [95% CI] | F1 repaired / control, diff [95% CI] | control - original [95% CI] | control flips to correct / to wrong |
| --- | ---: | ---: | --- | --- | --- | --- |
| extraction | 18 | 0 | +0.667 [+0.444, +0.889] | 0.792 / 0.069, +0.722 [+0.526, +0.900] | +0.000 [+0.000, +0.000] | 0 / 0 |
| sharding | 0 | — | — | — | — | — |
| all | 18 | 0 | +0.667 [+0.444, +0.889] | 0.792 / 0.069, +0.722 [+0.526, +0.900] | +0.000 [+0.000, +0.000] | 0 / 0 |

## Sensitivity: delivery at recall >= 0.5 (post-hoc threshold, amendment 3)

| cell | undelivered cases | delivered | no unit >= 0.5 | correct: repaired / original | diff [95% CI] | F1: repaired / original | diff [95% CI] | gain / loss / tie |
| --- | ---: | ---: | ---: | --- | --- | --- | --- | --- |
| extraction | 21 | 13 | 8 | 3 / 0 | +0.143 [+0.000, +0.286] | 0.182 / 0.032 | +0.149 [+0.030, +0.297] | 3 / 0 / 18 |
| sharding | 20 | 12 | 8 | 2 / 0 | +0.100 [+0.000, +0.250] | 0.178 / 0.078 | +0.100 [+0.000, +0.250] | 2 / 0 / 18 |
| all | 41 | 25 | 16 | 5 / 0 | +0.122 [+0.024, +0.220] | 0.180 / 0.055 | +0.125 [+0.044, +0.222] | 5 / 0 / 36 |

All undelivered cases are in this denominator: a case with no unit at or above 0.5 counts as a zero difference.

The post-hoc label applies to this table only; amendment 4 below is a separate frozen arm.

## Full-evidence routing for the sharding cell (amendment 4)

The flagged agent is given the concatenation of all the instance's source supports, then the same frozen extraction step and gate. Gold-free: no fact text is shown.

| cases | delivered | delivered 95% CI | undelivered | correct repaired / original | diff [95% CI] |
| ---: | ---: | --- | ---: | --- | --- |
| 20 | 1 | 0.001-0.249 | 19 | 0 / 0 | +0.000 [+0.000, +0.000] |

The control re-aggregates the unchanged board with the same prompt, model and token budget. Control - original measures re-run drift; repaired - control is the delivered units alone.

## Delivery

Delivery is the frozen `delivery_gate` (fact token recall >= 0.8). Undelivered cases never reach the board. The gate certifies that a unit states the flagged fact; it does not certify that the passage contains it. For the delivered units, the shard carries the unit text at recall >= 0.8 for 16 of 19 units (>= 0.5 for 19).

For the 18 delivered extraction cases the flagged fact sits in the flagged agent's own passage at recall >= 0.8 in 15 and >= 0.5 in 18, so these repairs recover a fact the shard did carry.

## What this cannot show

A single-slot repair adds the fact the audit flagged. It does not separate "the audit picked the right slot" from "any correct fact added would have helped", and it does not re-run the full upstream protocol: extraction and re-routing are the repaired stages, the downstream selection and aggregation run on the existing board plus the delivered units.

The first sharding pass fed the flagged agent's own passage, which by definition lacks the fact, and delivered nothing; its 20 calls ($0.002528) and records in `results_sharding_pass1.jsonl` stay on record.

## Ledger
Spend $0.011524.
