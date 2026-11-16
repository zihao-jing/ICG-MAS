# B6c: verbatim extraction on the six supported sharding cases

2026-11-15. Frozen before any call. Cap **$0.50**, one chunk.

## Population

Exactly the six sharding cases whose flagged fact a supplied passage states at the gate threshold (recall
>= 0.8), listed in the B6 report: `2hop__304852_758385`, `2hop__342746_679190`, `2hop__128342_375952`,
`2hop__71294_494136`, `3hop1__454441_55349_651302`, `2hop__46213_494136` (Gemma and GPT-4o-mini traces). The
other 14 sharding cases stay labelled unsupported and are not run.

## The fix

The corrected single-passage pass delivered none of the six because the extractor paraphrases. This arm
requires **verbatim quotation**: the extractor returns up to 3 sentences copied exactly from the passage that
states the fact, with no paraphrase and no added words. The passage is the same one the supported label uses
(max gate recall). Extraction prompt, frozen and hashed before any call:

- system: `You quote evidence verbatim. Copy sentences exactly as they appear; never paraphrase, summarise, or add words.`
- user: the passage, the question, and `Quote up to 3 sentences from the passage that bear on the question. Copy each one exactly. Number them 1..3.`

Everything else is unchanged: the trace's own model, temperature 0, 512 tokens, the frozen `delivery_gate`
(recall >= 0.8) and the same aggregation call on the original board plus delivered units.

## Calls and scoring

6 extraction calls plus at most 6 aggregation calls. Delivered count out of 6 with a Clopper-Pearson 95%
interval; for delivered cases, exact correctness against the same trace's baseline.