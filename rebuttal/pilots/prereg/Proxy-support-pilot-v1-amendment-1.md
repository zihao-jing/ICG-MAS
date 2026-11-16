# Amendment 1 to Proxy-support-pilot-v1: output-shape tolerance

2026-11-15, written after the first fact-generation pass and before any equivalence or audit call.
The frozen prompt, the instance list and the model settings are **not changed**. This amendment fixes
two output-interface defects found when reading the generated facts.

## What happened

7 of 10 traces produced a valid object on the first pass. The other 3 returned complete, usable fact
content in shapes the parser rejected:

- 2 traces (`coh/gpt4omini/3hop1__389761…`, `coh/gpt4omini/2hop__25396…`): a top-level map keyed by
  fact_id (`{"f1": {"text": …, "source_ids": […]}, …, "support_sets": [[…]]}`) instead of
  `{"facts": [{"fact_id": …}], "support_sets": …}`. The facts and support sets are complete.
- 1 trace (`inj/gpt4omini/2hop__17455…`): correct shape, but `source_ids` cited document titles inside a
  supplied shard (`"agent-1: Hellenistic period"`) rather than the supplied shard id `agent-1`.

Neither is a change in fact content; both are interface mismatches between the model's JSON and the
parser.

## Amended parser rule

- Accept either shape: the `{"facts": [...]}` list, or a flat map of fact_id → `{text, source_ids}` with
  `support_sets` beside it. In both cases every fact must still have `text` and `source_ids`, and
  `support_sets` must be present, nonempty, and reference existing fact ids.
- `source_id` normalisation: an entry that is exactly a supplied unit id is kept; an entry that begins
  with a supplied unit id followed by a separator (`:`, `::`, `/`, ` `) is normalised to that unit id;
  any other entry fails the call. This preserves which shard the model cites and never invents a shard.
- Rejected parses still count as generation attempts and stay in `calls.jsonl`. Traces that failed are
  regenerated under the unchanged prompt with retry keys; the failed attempts remain on record.

## Why this is not tuning on outcomes

The prompt, population, model, temperature and token limit are unchanged. The amendment only lets the
parser read the same model output in two equivalent shapes and keeps the shard identity the model
intended. No fact text, no verdict, no label was altered by hand.