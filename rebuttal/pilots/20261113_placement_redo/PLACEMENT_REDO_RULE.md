# Frozen rule: placement by redoing the blamed stage (item 7)

Written 2026-11-13 before any call. Stage: relay checkpoint (the agent's
transmission) with the final aggregation held fixed; pilot only. Cap $5; every
call logged.

## Cases

The 30 injected-distortion cases
(`20261113_injected_distortion/accepted.json`), where the faulty stage is the
relay checkpoint by construction and the faulty agent is the owner of the
corrupted board unit. Pilot: 10 cases, sorted by
`sha256('43|redo|' + instance_id + '|' + model + '|' + unit_id)`.

## Stronger model

Gemini 3.6 Flash via OpenRouter ($0.75/M input, $3.75/M output), temperature 0.
The local agents are Gemma-4-31B, GPT-4o-mini and Qwen-235B.

## Arms (identical models and prompts except the agent whose step is redone)

For each case:

- **diagnosed**: the stronger model redoes the transmission step of the agent
  that owns the corrupted board unit. It sees only that agent's source shard
  (context text) and the question, no gold and no other agent's text; it
  writes the evidence statement that agent should have transmitted.
- **random**: the stronger model redoes the transmission step of a random
  other agent (seed 43, sorted agent ids), with that agent's own shard only;
  the statement replaces an existing unit from that agent.

In both arms the re-transmitted statement replaces **one** existing board unit
of that agent (the corrupted unit in `diagnosed`; the first unit in `random`),
so the board size is unchanged. The final aggregation is then called with the
original trace's model and the frozen aggregation prompt, temperature 0.

## Outcome

Exact match against the stored gold, paired by case; the diagnosed arm is
compared with the random arm (descriptive, n=10). The fact that the diagnosed
unit was the injected corruption is not used by either call; only the case
selection uses it. No oracle text, no full run.

## Cost

20 transmission calls + 20 aggregation calls, cap $5, ledger in this
directory. If the cap is reached the remaining cases are skipped and reported.