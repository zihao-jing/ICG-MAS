# Q1 second sample: failure-enriched, disjoint from the first three

2026-11-15. Rule `Q1-second-sample.md` (sha `49e56cf8...`). Claude Haiku 5.5, validated point prompt on both
sides (`a1: text`), 30 traces drawn from the 37 remaining wrong-instance traces, disjoint from the 31 already
used. 60 gold and 228 proxy calls, 288 result calls, 0 invalid, **$0.071431**, cap $0.50.

## Agreement

| sample | traces with both stages | agree | rate [95% Wilson] |
| --- | ---: | ---: | --- |
| second sample, disjoint | 30 | 6 | 0.200 [0.095, 0.373] |

## Confusion, proxy stage (rows) by gold stage (columns)

| proxy \ gold | extraction | transmission | aggregation |
| --- | ---: | ---: | ---: |
| extraction | 4 | 0 | 0 |
| transmission | 0 | 0 | 0 |
| aggregation | 24 | 0 | 2 |

Gold: 28 extraction, 0 transmission, 2 aggregation. Proxy: 4 extraction, 0 transmission, 26 aggregation.

Reported separately from the earlier samples; it overlaps none of their 31 traces. The direction matches the
earlier runs: the proxy audit reads its own fact set as complete and names aggregation where the gold audit
finds the gold fact absent from the pool.

## Ledger

$0.071431.
