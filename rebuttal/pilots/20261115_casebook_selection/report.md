# Casebook example selection under the new sharding rule

2026-11-15. Rule `prereg/Casebook-selection-v1.md`, written before the selection. Selection is $0: it reads
the stored audit labels (`20261115_sharding_semantic/canonical.json`, `results.jsonl`) and the stored Gemini
judge labels (`20261113_attribution_comparison/results_v2.json`, field `judge.stage`).

## Rule

Eligible cases are the 89 known-stage cases where the new-rule audit with Gemini 3.6 Flash and the Gemini
3.6 Flash judge both resolve a stage and the labels differ. Order by full case key, ascending; take the first
two. No filtering on which side is correct and no substitution after the fact.

## Selection (31 eligible)

| case | audit Gemini | judge Gemini | known stage |
| --- | --- | --- | --- |
| `coh/gemma31b/2hop__157285_556157` | extraction | sharding | extraction |
| `coh/gemma31b/2hop__207597_73244` | extraction | sharding | extraction |

In both, the audit names extraction, the judge names sharding, and the known stage is extraction.

## The two cases currently in the text

`2hop__723404_58556` and `2hop__50068_494136` were chosen in the previous pass by no rule fixed in advance.
Under the new shard rule they change: `723404` is now sharding in the Gemini audit, and `50068` is sharding
in the Qwen audit and extraction in the Gemini audit. They are not the fixed-rule selection and should not
be presented as such. The reviewer text stays unchanged while attribution text is on hold.