# Audit-guided versus judge-guided repair, same budget (frozen before any call)

2026-11-15. Cap **$2.00**. Paper models only: Gemini 3.6 Flash makes the repair call; the trace's own model
(Qwen-235B, GPT-4o-mini, Gemma-4-31B) answers.

## Population

The 30 injected cases of the 89-case known-stage set. Each has one corrupted board unit, known agent, and a
gold answer from the accepted-corruption record. Both arms see the same corrupted trace.

## Arms, one repair call and one answer call each

- **Audit arm:** the audit's diagnosis supplies the stage (transmission) and the missing fact. The repair prompt
  names that fact and asks the model to quote the supporting sentence from the agent's own shard. The corrupted
  board unit is replaced by that quote; the rest of the board is unchanged.
- **Judge arm:** the stored judge label supplies the stage and the agent only, no fact. The repair prompt is the
  standard extraction prompt on that agent's shard plus the question; all of that agent's board units are
  replaced by the extracted list; the rest of the board is unchanged.

Same number of calls. The audit arm has the fact; the judge arm does not. That is the comparison.

## Outcome

Exact match against the gold answer (F1 = 1.0), both arms paired on the same case. McNemar exact test on
discordant pairs, plus a case bootstrap for the difference. Clopper-Pearson intervals on each arm's count.

## Prompt hashes

Both prompts frozen in `calls.jsonl` as `system_sha256` before their first call; the script's constants are
hashed into `build_manifest.json`.