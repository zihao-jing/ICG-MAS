# Q1 rerun with the validated renderer: gold vs proxy stage on the full population

2026-11-15. Rule `Q1-validated-rerun.md` (sha `1d3d1928...`). Claude Haiku 5.5, atom-level point prompt v1
(system sha `86d84ff6...`) rendered as in `per_fact_points_run.render` (`a1: text`); 31 unique `random_relay`
traces, 62 gold calls and 144 proxy calls, 206 result calls, 0 skips, 0 invalid replies, **$0.054741**, cap $0.50.

## Samples: two distinct trace sets and one repeat

Samples 2 and 3 are the same 30 traces (overlap 30), so the run has two distinct trace sets and one repeat of the second. Sample 1 shares 29 of its 30 traces with that set.

## Agreement, full population

| sample | traces with both stages | agree | rate [95% Wilson] |
| --- | ---: | ---: | --- |
| sample1_uniform | 30 | 6 | 0.200 [0.095, 0.373] |
| sample2_coarse | 30 | 6 | 0.200 [0.095, 0.373] |
| sample3_atom | 30 | 6 | 0.200 [0.095, 0.373] |

Every trace is scored; the parser filter is no longer needed. The repeat (sample 3) scores the same traces as sample 2 by construction. Sample 1's one unique trace and sample 2's one unique trace are both aggregation/aggregation, which is why all three rows give identical counts.

## Overlap of the three samples

| pair | shared traces |
| --- | ---: |
| sample 1 and sample 2 | 29 |
| sample 1 and sample 3 | 29 |
| sample 2 and sample 3 | 30 |

Sample 1's only unique trace is `2hop__363216_787353`; sample 2's is `3hop1__106042_64399_59680`; both are scored
aggregation on both sides. The 29 shared traces therefore give the same contribution to all three samples, and the
single differing trace contributes the same pair, so 6/30 in each is arithmetic, not a copied result. The scoring
reads each sample's own id list.

## Beside the filtered result

| sample | legacy renderer, filtered | validated renderer, full population |
| --- | --- | --- |
| sample1_uniform | 3/13 = 0.231 [0.082, 0.503] | 6/30 = 0.200 [0.095, 0.373] |
| sample2_coarse | 2/11 = 0.182 [0.051, 0.477] | 6/30 = 0.200 [0.095, 0.373] |
| sample3_atom | 4/15 = 0.267 [0.109, 0.520] | 6/30 = 0.200 [0.095, 0.373] |

The filtered rates were computed on 13, 11 and 15 of 30 traces and carried wide intervals; on the full population the
rate is lower and the interval tighter. The filtered sample was not biased in the other direction.

## Confusion, proxy stage (rows) by gold stage (columns), each sample

| proxy \ gold | extraction | transmission | aggregation |
| --- | ---: | ---: | ---: |
| extraction | 2 | 0 | 2 |
| transmission | 2 | 0 | 0 |
| aggregation | 20 | 0 | 4 |

Gold: 24 extraction, 0 transmission, 6 aggregation. Proxy: 4 extraction, 2 transmission, 24 aggregation.

The direction is unchanged from the filtered result: the proxy audit reads its own short fact set as complete and
names aggregation on 24 of 30 traces, while the gold audit names extraction on 24 of 30.

## Superseding note

These labels replace the Q1 gold labels and the atom-level proxy labels above as the Q1 result; the older reports
are kept as the legacy record. The disagreement-cause diagnosis (`20261115_proxy_vs_gold_stage/diagnosis.md`) was
computed on the legacy pair and has not been recomputed on this run.

## Ledger

$0.054741.
