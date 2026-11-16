# UEGh Q1: gold-fact audit stage, sample 3 (enriched at atom level)

2026-11-15. 30 `random_relay` MuSiQue traces (instances whose `score_ranked_relay` run is wrong) selected for at
least one gold atom that fails the lexical recall test at extraction or board; gold atoms labelled at both
checkpoints with the point labeller (Haiku 5.5); 60 calls, $0.031945, cap $0.30.

## Sample identity

The atom-level filter returned the same 30 traces as sample 2 (the whole-support filter): 30/30 overlap, so this is
a repeat measurement of the same population, not a new draw. Its stage totals move by at most two traces per class.

## Correction: the checkpoint totals differed because the keys were not validated

All three samples first scored 30/30 aggregation (dict read as a list). The second rescore read the dict but counted
whatever keys the model returned; those key sets differ between checkpoints because the Q1 renderer passed the atom
texts without ids, and the model sometimes dropped atoms, substituted another sentence, or answered
`"<atom_id>"`. Checkpoints are now accepted only if they validate under the frozen parser (exact gold atom key set,
valid statuses, list `unit_ids`); the stage needs both checkpoints. Totals agree by construction.

## Validity

| | sample 3 |
| --- | ---: |
| checkpoints labelled | 60 |
| checkpoints failing the parser | 19 |
| traces with both checkpoints valid (traces) | 15 of 30 |
| atoms summed over valid traces (atoms; the same total at both checkpoints) | 63 |

## Statuses over the valid checkpoints

| checkpoint | present atoms | partial atoms | absent atoms | total atoms |
| --- | ---: | ---: | ---: | ---: |
| extraction | 21 | 12 | 30 | 63 |
| board | 20 | 13 | 30 | 63 |

## Gold audit stage

| stage | traces (absent only) | traces (absent or partial) |
| --- | ---: | ---: |
| extraction | 11 | 15 |
| transmission | 0 | 0 |
| aggregation | 4 | 0 |

15 traces scored, 15 lost to the parser. A gold audit stage exists for far fewer traces than the sample size
because most labeller replies do not validate; the all-extraction tie was partly the selection, but the selection
was lexical and this labelling is not.

Proxy-fact vs gold-fact stage agreement on this sample is in `../20261115_proxy_vs_gold_stage/report.md`.

**Superseded:** the validated-renderer rerun (`../20261115_q1_validated_rerun/report.md`) relabels gold and
proxy atoms with `a1: text` ids and scores all 30 traces per sample. The parser-filtered counts above are kept as
the legacy record.
