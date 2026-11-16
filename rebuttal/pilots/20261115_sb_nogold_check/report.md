# Silo-Bench proxy rerun without gold: three-trace check on the fixed prompt

2026-11-15. $0, no calls. Prompt `proxy_facts_prompt_v3_two_step.json` (sha `7210ce14…`). The prompt takes
exactly two fields, `{question}` and `{documents}`; there is no gold, answer or support field in either step.
Both steps were rendered with `scripts.sb_twostep_pilot.render_docs` and the rendered text compared with the
trace's gold support list, whitespace-normalised.

**The prompt is already question-plus-shards only, and the shards are the gold text.** Three traces, seed 43:

| trace | documents | gold supports | documents that are gold supports | gold supports found in the rendered prompt | documents equal the gold list |
| --- | ---: | ---: | ---: | ---: | --- |
| `qwen235b/SB/n5/summary_exchange/I-10_n5` | 5 | 5 | 5 | 5 | yes |
| `qwen235b/SB/n5/score_ranked_relay/III-26_n5` | 5 | 5 | 5 | 5 | yes |
| `qwen235b/SB/n10/score_ranked_relay/III-27_n10` | 10 | 10 | 10 | 10 | yes |

No `gold`, `gold_supports`, `answer` or `supports` field appears in the rendered prompt; the words "answer" in
the template are "needed to answer the question". Population level, as before: on 208 of 208 traces `documents`
and `gold_supports` are identical as ordered lists.

**Consequence.** In Silo-Bench each agent's shard is the document set the answer is drawn from, and on these
tasks every shard is needed, so "question plus shards" is "question plus the gold supports". Removing a gold
field cannot remove the gold text, because the only remaining field carries it. A no-gold rerun run on this
prompt would repeat the near-copy result: the generator is shown the very text the equivalence check compares it
against. The full run was not started; with this prompt it cannot answer the question it was meant to answer.
The only variant that would is one where the shards are not the gold supports (for example, a task whose agents
hold data the answer does not need), and that is a different benchmark construction, not a prompt fix.

## Shard-versus-gold check, all 208 traces ($0)

Records are counted as list elements or dict keys of each shard text (a text shard counts as one record).

| quantity | total |
| --- | ---: |
| traces | 208 |
| agent shards | 1,560 (5 per n5 trace, 10 per n10 trace) |
| records in the shards | 28,284 |
| gold supports | 1,560 |
| records in the gold supports | 28,284 |
| gold supports that are a whole shard | **1,560** |
| gold supports that are a subset of a shard's records | 0 |
| gold supports not found in any shard | 0 |

Every gold support is a whole agent shard, on every trace (208/208 have equal shard and gold record totals),
and the per-trace counts are in `shard_check.json`. Example, `qwen235b|SB|n5|summary_exchange|I-01_n5`
("Global Maximum"): 5 shards, 20 records each (agent-0's array is 20 numbers, agent-1's another 20, ...), and
5 gold supports, each one of those shards whole, 20 records each — the same text, same order, same records.

**Outcome: the gold supports are the whole shards, not a subset.** The gold-free proxy from full shard contents
would be the same input as the gold-based one on this benchmark, so the rerun is dropped. UEGh Q1 states the
consequence in one sentence: the critical facts are the task inputs themselves and no proxy is needed on
Silo-Bench.
