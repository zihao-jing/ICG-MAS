# Selection repair, volume-matched targeted request (frozen before any call)

2026-11-15. Cap **$0.50**, paper models only (`qwen/qwen3-235b-a22b-2507`, `openai/gpt-4o-mini`,
`google/gemma-4-31b-it`).

## Why

The earlier targeted request (R-sel) added up to two units to the board, so 38 of 52 pairs exceeded the 10%
token-volume band against the donor arm. This arm holds the board's unit count constant: the targeted request
**replaces** one board unit of the same agent instead of being appended, so the board the aggregator sees is the
same size as in the plain rerun.

## Population and inputs

The 52 tested traces and the frozen target requests of `20261114_selection_repair/actions.json` (unchanged).
Board, pool, question, gold and aliases as in that manifest.

## Arm

- **R-sel-replace**: from the target agent's board units, remove the last unit in unit-id order; add the first
  target request unit for the same agent; aggregate with the original model, the frozen aggregation prompt,
  `max_tokens=4096`, temperature 0.
- Cases where the target agent has no board unit are recorded as no-op and excluded from the paired contrast.

## Volume check

For every case the total board token count of this arm is compared with the plain rerun's board under the frozen
`volume_match` rule (±10%); the matched share is reported. The arm's design keeps unit count equal, not exact
token count.

## Outcome

Exact match against the MuSiQue gold answer, paired against the plain rerun's stored answers (case bootstrap,
2,000 draws, seed 43). If the paired effect is null, the report states the detectable effect size at n = 52
before any write-up.