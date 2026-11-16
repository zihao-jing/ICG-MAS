# B6d: bridge-aware extraction on the six supported sharding cases

2026-11-15. Frozen before any call. Cap **$0.20**, one chunk. Last sharding attempt.

## Why

B6c required verbatim quotation but the extractors screened sentences by whether they mention the question's
entities: 4 of 6 returned nothing and 2 quoted sentences that miss the bridge. This arm removes that screen.

## Population and inputs

The same six supported sharding cases and the same passages (the passage with the highest gate recall against
the flagged fact). Nothing else changes: the trace's own model, temperature 0, 512 tokens, the frozen
`delivery_gate` (recall >= 0.8), the same aggregation call on the original board plus delivered units.

## Frozen extraction prompt

- system: `You quote evidence verbatim. Copy sentences exactly as they appear; never paraphrase, summarise, or add words. Quote every sentence the question's reasoning chain needs, including sentences about intermediate entities, even when they do not mention an entity named in the question. Do not screen sentences out for irrelevance.`
- user: the passage, the question, and `Quote up to 5 sentences the question's reasoning chain needs, including bridge sentences about intermediate entities that do not appear in the question. Copy each one exactly. Number them 1..5.`

## Scoring

Delivered count out of 6 with a Clopper-Pearson 95% interval; exact correctness of delivered cases against
the trace's baseline. If it delivers 0 of 6, the sharding repair closes as a negative result: no gold-free
extraction on the supported passages delivers these bridge facts under the frozen gate, and the cause is the
extractor's own filtering/summarisation, not the passage.