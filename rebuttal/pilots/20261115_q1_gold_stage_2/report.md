# UEGh Q1: gold-fact audit stage, sample 2 (enriched by whole-support lexical loss)

2026-11-15. 30 `random_relay` MuSiQue traces (instances whose `score_ranked_relay` run is wrong) selected for a
gold support that fails the whole-support lexical recall test at extraction or board; gold atoms labelled at both
checkpoints with the point labeller (Haiku 5.5); 60 calls, $0.030552, cap $0.90.

## Correction: the checkpoint totals differed because the keys were not validated

The first scorer reported 30/30 aggregation (dict read as a list). The second rescore read the dict but counted
whatever keys the model returned, and those key sets differ between checkpoints because the Q1 renderer passed the
atom texts without ids. Checkpoints are now accepted only if they validate under the frozen parser (exact gold atom
key set, valid statuses, list `unit_ids`); the stage needs both checkpoints. Totals agree by construction.

## Validity

| | sample 2 |
| --- | ---: |
| checkpoints labelled | 60 |
| checkpoints failing the parser | 25 |
| traces with both checkpoints valid (traces) | 11 of 30 |
| atoms summed over valid traces (atoms; the same total at both checkpoints) | 50 |

## Statuses over the valid checkpoints

| checkpoint | present atoms | partial atoms | absent atoms | total atoms |
| --- | ---: | ---: | ---: | ---: |
| extraction | 16 | 7 | 27 | 50 |
| board | 16 | 7 | 27 | 50 |

## Gold audit stage

| stage | traces (absent only) | traces (absent or partial) |
| --- | ---: | ---: |
| extraction | 9 | 11 |
| transmission | 0 | 0 |
| aggregation | 2 | 0 |

11 traces scored, 19 lost to the parser. The selection makes extraction-heavy stages partly by construction: these
traces were chosen for a gold support the extraction pool did not lexically contain.

Proxy-fact vs gold-fact stage agreement on this sample is in `../20261115_proxy_vs_gold_stage/report.md`.

**Superseded:** the validated-renderer rerun (`../20261115_q1_validated_rerun/report.md`) relabels gold and
proxy atoms with `a1: text` ids and scores all 30 traces per sample. The parser-filtered counts above are kept as
the legacy record.
