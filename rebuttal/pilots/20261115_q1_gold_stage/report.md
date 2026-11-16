# UEGh Q1: gold-fact audit stage, sample 1 (uniform draw)

2026-11-15. 30 `random_relay` MuSiQue traces (instances whose `score_ranked_relay` run is wrong), drawn without
enrichment; gold supports labelled at the extraction and board checkpoints with the point labeller (Haiku 5.5);
60 calls, $0.030980, cap $1.50.

## Correction: the checkpoint totals differed because the keys were not validated

The first scorer reported 30/30 aggregation: it read the per-atom labels as a list while the labeller returns a
dict, so no atom could be absent. The second rescore read the dict but counted **whatever keys the model returned**
at each checkpoint. Those key sets differ: the Q1 renderer passed the atom texts without ids, and the model
sometimes echoed a different sentence, dropped atoms, or answered `"<atom_id>"`. So the two checkpoints were
labelled over different atom sets and their totals could not agree (108 vs 130 atoms).

Fixed at $0, no new calls: a checkpoint counts only if it validates under the frozen parser
(`per_fact_points_run.parse`: key set exactly equal to the trace's gold atom set, every status present/partial/
absent and `unit_ids` a list). The stage is derived only when both checkpoints validate. Totals now agree by
construction.

## Validity

| | sample 1 |
| --- | ---: |
| checkpoints labelled | 60 |
| checkpoints failing the parser | 22 |
| traces with both checkpoints valid (traces) | 13 of 30 |
| atoms summed over valid traces (atoms; the same total at both checkpoints) | 47 |

## Statuses over the valid checkpoints

| checkpoint | present atoms | partial atoms | absent atoms | total atoms |
| --- | ---: | ---: | ---: | ---: |
| extraction | 17 | 12 | 18 | 47 |
| board | 18 | 12 | 17 | 47 |

## Gold audit stage

| stage | traces (absent only) | traces (absent or partial) |
| --- | ---: | ---: |
| extraction | 10 | 13 |
| transmission | 0 | 0 |
| aggregation | 3 | 0 |

13 traces scored, 17 of 30 lost to the parser. Read as the audit stage computed from gold facts on the same
traces, not accuracy against a true stage. The sample supports a statement about 13 traces only.

Proxy-fact vs gold-fact stage agreement on this sample is in `../20261115_proxy_vs_gold_stage/report.md`.

**Superseded:** the validated-renderer rerun (`../20261115_q1_validated_rerun/report.md`) relabels gold and
proxy atoms with `a1: text` ids and scores all 30 traces per sample. The parser-filtered counts above are kept as
the legacy record.
