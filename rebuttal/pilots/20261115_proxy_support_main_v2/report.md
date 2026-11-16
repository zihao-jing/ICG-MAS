# 608 run under the amended output caps: pilot and truncation check (stopped)

2026-11-15. Rule `Proxy-support-caps-v1.json` (sha `2fad0404…`), frozen before any call: facts 4,096 → 8,000
tokens, equivalence check 3,000 → 8,000, checkpoint label 2,000 → 8,192. Population, prompts and parsers
unchanged. Line cap $7.5; prior line spend $1.374826.

## Pilot: first 20 traces (all SB summary-exchange)

Spend **$0.343866**. 19/20 fact sets valid, 17/20 equivalence checks valid.

**Truncation persists: 3 of 20 traces (15%) still hit a cap after the raise.**

| trace | stage | what happened |
| --- | --- | --- |
| `II-19_n5` | facts | two attempts cut at 8,000; the third returned 477 tokens and still failed validation |
| `III-22_n5` | equivalence | both attempts cut at 7,996; the fact set itself was fine (4,905 tokens) |
| `III-24_n5` | facts + equivalence | attempt 1 emitted **facts f1…f1,300+** before the cut; attempt 2 succeeded at 6,515 tokens; both equivalence attempts cut at 7,996 |

Cause: not the cap value but **fact granularity**. On Silo-Bench numeric and graph tasks the proxy decomposes
each element into its own fact — one trace reached 1,300 facts. No economical cap covers that (a 1,300-fact
equivalence check alone is ~64k output tokens), so raising the cap to 16k or 32k would cost far more than the
$7.5 line and still be unbounded. The truncation check fires here: 15% > 2%, so the run stopped before the
remaining 588 traces, as instructed.

## Status

- Population rate: **not produced** (the run stopped at the truncation check).
- The 20 pilot traces stay in this directory, unused for reporting.
- The earlier 81-trace partial stays on record, unused.

## Ledger

Spend $0.343866; cumulative $92.815744.
