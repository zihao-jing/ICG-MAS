# Input-presence (sharding) check in the audit diagnosis

Rule `SHARDING_RULE.md` (sha256 `fe5f9a8ec227`) frozen before this run. Zero model calls; spend $0.000000. Old diagnoses stay on record in the files named below; the old `diagnose` function is unchanged.

## Missing-fact cohort (extraction stage)

Cohort: 69 clean extraction-omission traces over 59 unique instances; presence labels and targeted fact from `20261112_missing_fact_repair/presence.json` (frozen presence rule, including the recorded manual read).

| level | old diagnosis | new sharding | new extraction | moved |
| --- | ---: | ---: | ---: | ---: |
| traces | 69 | 27 | 42 | 27/69 (39.1%, 95% CI 27.6-51.6) |
| instances | 59 | 20 | 39 | 20/59 (33.9%, 95% CI 22.1-47.4) |

## E1 anchor diagnoses (relay checkpoints)

Population: the 8 valid E1-anchor matcher records whose frozen diagnosis is `extraction_omission` (30 instances x 3 models; failed records excluded). Source file: `rebuttal/results/batch1/E1_matcher_anchor/matcher/`. Targeted facts are the `extraction_omission` facts in each trace's chosen support set; a fact is in-shard if any source shard contains it under the frozen presence rule.

| level | old diagnosis | new sharding | new mixed | new extraction | moved |
| --- | ---: | ---: | ---: | ---: | ---: |
| traces | 8 | 0 | 2 | 6 | 2/8 (25.0%, 95% CI 3.2-65.1) |

Per-fact shard labels: **8 of 10** targeted facts are present or partial in their source shard, **2** are absent in every source shard.

## Main-table diagnoses (2,400 traces, relay checkpoints)

Population: the 216 valid traces in the Stage 2 main-run matcher set (`rebuttal/results/batch1/expansion_stage2/matcher/`, 2,400 traces over three models) whose frozen diagnosis is `extraction_omission`. Targeted facts and source shards as in the rule. No new matcher call.

| level | old diagnosis | new sharding | new mixed | new extraction | moved |
| --- | ---: | ---: | ---: | ---: | ---: |
| traces | 216 | 28 | 9 | 179 | 37/216 (17.1%, 95% CI 12.4-22.8) |

Per-fact shard labels: **235 of 275** targeted facts are present or partial in their source shard, **40** are absent in every source shard. By model: gemma31b 12/126 moved, gpt4omini 14/57 moved, qwen235b 11/33 moved.


## Anchor detail

- 2hop__142621_225454 / gemma31b: old extraction, new **extraction_omission**; f3: partial (0.67)
- 2hop__28287_89399 / qwen235b: old extraction, new **extraction_omission**; f3: present (1.00)
- 3hop1__147225_30587_83479 / gemma31b: old extraction, new **extraction_omission**; f2: present (1.00)
- 3hop1__147225_30587_83479 / gpt4omini: old extraction, new **extraction_omission**; f2: present (1.00)
- 3hop1__147225_30587_83479 / qwen235b: old extraction, new **extraction_omission**; f4: partial (0.60)
- 3hop1__640171_228453_86925 / gemma31b: old extraction, new **extraction_omission**; f3: partial (0.50)
- 4hop1__814349_624859_355213_203322 / gemma31b: old extraction, new **mixed_sharding_extraction**; f3: partial (0.67), f4: absent (0.33)
- 4hop1__814349_624859_355213_203322 / gpt4omini: old extraction, new **mixed_sharding_extraction**; f3: partial (0.67), f4: absent (0.33)

## Reading

The old diagnosis assumed the fact was in the agent's input. In the missing-fact cohort the frozen presence labels put 20 of 59 instances outside the target agent's shard, so those losses happen at sharding, not extraction; the remaining 39 stay extraction losses (33 present, 6 partial). In the main-table diagnosis set, 37 of 216 extraction diagnoses change (to sharding or mixed). In the E1 anchor, 2 of 8 change. Because the presence rule is lexical and can read co-located tokens as presence, the sharding count is a lower bound. The old diagnoses remain in `presence.json` and the matcher records.
