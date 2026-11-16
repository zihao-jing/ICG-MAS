# MuSiQue hop-anchor set A: reconciliation with the 6/30 run, and 62/81 cross-tab

2026-11-15. $0, no model calls. Script `scripts/mq_hop_reconcile.py`; numbers in `reconcile.json` (same folder).

## 1. Set A: .172 vs .200

Population: the same 30 instances (`20261115_q1_second_sample`). Gold stages are identical on 30/30 traces.
Only the proxy facts differ: the 6/30 run used prompt v1 facts, the hop-anchor check used v4 (hop-anchored) facts.

| Run | Proxy facts | Agreement | Denominator | Rate |
| --- | --- | --- | --- | --- |
| 6/30 run (`20261115_q1_second_sample`) | v1 | 6/30 | 30 | .200 [.095, .373] |
| Hop-anchor check, set A (`20261115_mq_hop_anchor`) | v4 | 5/29 | 29 (1 trace dropped) | .172 [.073, .336] |
| Same, dropped trace counted as disagreement | v4 | 5/30 | 30 | .167 |

The difference is 8 traces whose proxy stage changes under v4: 3 gain agreement, 4 lose it. One trace
(`2hop__458672_20057`) is dropped because one of its proxy fact labels is invalid. Net change 6 to 5.

Neither figure is a pass or fail input. The pass bar used sets B and C only.

## 2. 62/81 cross-tab (proxy stage vs gold-audit stage, 81 traces)

Source: `20261115_proxy_support_89/results.json`, stage matrix.

| Question | Count |
| --- | ---: |
| Proxy names an early loss (extraction or sharding) | 52 |
| of which the gold audit also names an early loss | 48 (92%) |
| of which the gold audit does not (proxy names extraction, gold names transmission) | 4 |
| Gold audit names an early loss | 58 |
| of which the proxy misses it (names transmission or aggregation) | 10 |

The 10 misses: 5 named transmission, 5 named aggregation.

## 3. The same breakdown on the 6/30 set

Source: `20261115_q1_second_sample/score.json`, confusion.

| Question | Count |
| --- | ---: |
| Proxy names an early loss (extraction) | 4 |
| of which the gold audit also names extraction | 4 (100%) |
| Gold audit names extraction | 28 |
| of which the proxy misses it (names aggregation) | 24 |

## Reading

Confirmation is high on the 62/81 set and on the 6/30 set, but the 6/30 set misses 24 of 28 gold losses, against
10 of 58 on 62/81. The misses are not all a final-step error on 62/81 (5 of 10 name transmission).
