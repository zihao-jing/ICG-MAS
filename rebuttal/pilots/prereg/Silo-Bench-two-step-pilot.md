# Silo-Bench two-step proxy pilot

2026-11-15. Frozen before any call. Cap **$1.50**, chunks of $1 or less. Prompt version
`proxy_facts_prompt_v3_two_step.json`, hashed in the manifest before the first call.

## Why

Under the granularity-fixed proxy (v2 prompt) the 208-trace Silo-Bench run truncated 6 of 208 (2.9%), which
tripped the 2% stop rule, and the facts were coarse. Both point at the table rows: the facts call sees the whole
table at once and enumerates across rows. This pilot splits the work: first choose the rows the question needs,
then write atomic facts only for those rows.

## Steps (two model calls, then the existing checks)

1. **Selection.** Qwen-235B, temperature 0, 800 tokens: given the question and the table entries, return
   `{"needed": [entry ids]}`. Every listed id must be a supplied entry id; the list must be non-empty. Up to 3
   attempts.
2. **Facts.** The frozen v2 facts prompt, unchanged, applied to the **selected entries only** (question and
   documents slots as in v2). Qwen-235B, 8,000 tokens, up to 3 attempts, the frozen `validate_facts` parser.
3. **Equivalence.** The frozen `proxy_support_equiv_prompt_v1.json` with Gemini 3.6 Flash against the gold
   supports, 8,000 tokens, so each generated fact is checked against gold.
No audit labels: this pilot tests the facts stage only.

## Population

20 of the 208 Silo-Bench traces under the fixed proxy, sampled with seed 50 (Python `random.Random(50)`,
sorted keys, `sample(20)`), frozen with its own sha. Gold supports are 5 or 10 per trace.

## Bars (fixed before calls)

- **Truncation**: a call whose completion reaches its token cap counts as truncated. The run stops as soon as
  the truncated share exceeds **2%** (with 20 traces, the first truncated trace stops it).
- **Granularity against gold**: mean facts per trace **<= 1.2 x the mean gold supports per trace in this
  sample** (recorded in the manifest before calls), and **no trace above 30 facts**.
- Both bars must pass for the pilot to pass; equivalence is reported with a Clopper-Pearson interval but is not
  a pass bar at this size.

## What the full run would do

If the pilot passes, Silo-Bench is run as its own population rate under the same two-step prompt, within about
$4, with the same truncation stop.