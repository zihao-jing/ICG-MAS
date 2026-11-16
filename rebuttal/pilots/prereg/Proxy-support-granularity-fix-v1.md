# Proxy-support granularity fix (8e): rule and before/after check

2026-11-15. Frozen before any call of this step. Separate from the $7.5 population line; its own cap is **$1.5**.
No change to the population, the equivalence prompt, the labeller prompt or the parsers.

## Cause, read from the 20 amended-cap pilot traces

Fact counts per trace in `20261115_proxy_support_main_v2/facts.json`:

| trace | facts | shape |
| --- | ---: | --- |
| `III-24_n5` | 160 (1,300+ in attempt 1) | one fact per edge: "Agent 0 holds edge [0, 30]" |
| `III-22_n5` | 125 | one fact per array element: "Agent 0 holds the value 618" |
| `II-17_n5` | 74 | one fact per array element: "The fifth element of agent-0's array is 69" |
| `II-18_n5` | 40 | one fact per element |
| `I-03_n5` | 20 | 4 per agent |
| the 13 small traces | 5–10 | one fact per agent |

`II-19_n5` never produced a valid fact set: three attempts cut at 8,000 tokens.

So the truncation is a **granularity** effect, not a cap effect: the proxy decomposes each numeric or graph record
into one fact per element, so the fact list and the equivalence output grow with the size of the record (a 30-value
array × 5 agents = 150 facts). Raising the cap cannot fix an unbounded count; the pilot showed 15% of traces still
truncate at 8,000.

## Fix (gold-free)

`proxy_facts_prompt_v2.json` (sha recorded in the build manifest), one prompt amendment:

- a fact is a claim, not a cell: one fact per record (array, edge list, table row), stating the record as a whole;
- do not emit one fact per element, index or edge;
- emit only the records and claims the question needs; do not transcribe unused records.

`support_sets` semantics, atomicity of ordinary claims, the parser and the caps are unchanged.

## Traces

Both arms run on the same 20 Silo-Bench trace/protocol rows, drawn before any call of this step:

- **truncated set (10)**: rows with a truncation event in either prior run (old rule at 4,096/3,000 or amended rule at
  8,000), 47 candidates, drawn with seed 44.
- **non-truncated set (10)**: rows that completed both stages under the amended rule in the 20-trace pilot, 17
  candidates, drawn with seed 44.

Both arms run **under the amended caps** (facts 8,000, equivalence 8,000 tokens), so the only difference between
arms is the facts prompt. The before arm is re-run, not taken from the old logs, so the cap is held constant.

## What is measured

- Trace-level truncation: a trace counts as truncated when any stage exhausted its attempts without a valid JSON
  output and the last attempt's completion hit the cap.
- Fact count per trace (the granularity quantity).
- Equivalence: fact-level equivalent rate against the gold supports, Clopper-Pearson 95% CI, plus a trace-clustered
  bootstrap (2,000 draws, seed 43).
- Spend, every call logged.

## Validation rule

The fix validates if, on the 20 traces:

1. truncation after ≤ 2% (0 or 1 of 20) — the same 2% bar the population run is held to; and
2. equivalence after is not worse than before: the after point estimate ≥ before point estimate − 5 points, and the
   after 95% CI lower bound ≥ .65.

If it validates, Silo-Bench runs under the fixed proxy as its own population rate inside the remaining line cap. If
it does not, Silo-Bench stays out and the report names the cause and this fix. No further fix attempt without
approval.