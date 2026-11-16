# Shard presence by statement, not token overlap (frozen before any call)

2026-11-15. Third rule applied to the same 89 known-stage cases, so anything it gains is post-hoc. Cap **$1.00**.

## The problem

The current input-presence check (`src/audit/sharding_check.py`) calls a fact present in a shard when any single
evidence sentence reaches token recall 0.8 against it, and labels a trace `sharding_omission` when, for the facts
missing from the extraction pool, no source shard is present. Token overlap counts as presence, so a shard that
merely shares words with the fact blocks the sharding re-attribution and the trace stays labelled extraction.

## The rule

A fact counts as **present in a shard only if the shard's passage states it**: every atom of the fact, with the
same entities, values, dates, direction and qualifiers. Word overlap alone never counts.

- Atoms are the fact split by the frozen splitter (list elements, dict keys, sentences).
- One call per (case, fact): Claude Haiku 5.5, the atom-level presence prompt `per_fact_points_prompt_v1.json`
  (validated on other checkpoints at κ .847 and .780; **not validated at the shard checkpoint**, which is why this
  is a sensitivity rule), temperature 0, all of the fact's source-agent shard passages as the entries.
- **present**: every atom present. **partial**: at least one atom present and not all. **absent**: none.
- Stage mapping unchanged from the current rule: if every missing fact is `absent` from its shards, the trace is
  `sharding_omission`; if some are, `mixed_sharding_extraction`; otherwise `extraction_omission`. Both sharding
  labels map to the sharding stage. A fact that was lexically `present` and is now `partial` therefore does not
  move the trace by itself; only a fact that is now `absent` can.

## Population and cells

The 89 known-stage cases (59 cohort, 30 injected), both audit cells: the Gemini carrier-labeller cell (61/89 old)
and the Qwen carrier-labeller cell (57/89 old). Facts are the frozen Qwen fact sets; carriers are the stored
design-A carrier records; shards are the trace packages' source contexts.

The check runs once per (case, fact) and is shared by both cells, since the facts and shards are the same.

## What is reported

Old and new 2×2 per audit cell; the confusion movement among the sharding-known cases the audit called
extraction; any correct case that breaks; the effect on the sharding repair (0 of 6 supported cases); spend.