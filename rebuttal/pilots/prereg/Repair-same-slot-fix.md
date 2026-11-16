# Same-slot repair, symmetric prompt (frozen before any call)

2026-11-15. Fix for the prompt asymmetry in `20261115_repair_sameslot`: the two arms had different system prompts
("states the given fact" against "most relevant to the question"), so the audit arm was asked to quote a sentence
stating a fact that its evidence may not restate. Cap **$0.50**.

## Design

30 injected cases, both arms, the same corrupted unit and agent as before (`results.jsonl` of the first run).

- System prompt, identical for both arms: "You are an evidence repair assistant. Quote the single sentence from
  the agent's private evidence that best supports answering the question. Output one line, the quoted sentence
  only, no preamble."
- User prompt, judge arm: `Question: ...\nAgent N evidence:\n<shard>`.
- User prompt, audit arm: the judge prompt plus the final line `Fact the evidence should state: <fact>`.

The shard, slot, corrupt unit, aggregation model and answer prompt are unchanged; the fact is chosen as before
(the Qwen fact whose `source_ids` name the agent). Exact match remains answer F1 == 1.0 against the gold answer.

## Report

Both runs side by side, discordant pairs, McNemar exact p, paired difference with a 2,000-draw bootstrap interval,
and the faithful-unit collateral.