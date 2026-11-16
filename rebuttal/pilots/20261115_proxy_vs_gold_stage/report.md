# Proxy-fact vs gold-fact audit stage agreement

**Superseded by the validated-renderer rerun** (`../20261115_q1_validated_rerun/report.md`), which scores all 30 traces per sample; the filtered rows below stay as the legacy record.

2026-11-15. Rule `Proxy-vs-gold-stage.md` (sha `cb89d3f5...`), amendment 1 (sha `fe4ff406...`). No calls, $0. The quantity is agreement between two audit computations on the same traces, not accuracy against a true stage. Both sides are labelled by Claude Haiku 5.5 (gold: atom-level point prompt v1; stored proxy labels: fact-level prompt v3; atom-level proxy fix: prompt v1).

| sample | gold stage | both stages | agree | rate [95% Wilson] | no proxy stage |
| --- | ---: | ---: | ---: | --- | ---: |
| sample1_uniform | 13 | 12 | 1 | 0.083 [0.015, 0.354] | 1 |
| sample2_coarse | 11 | 10 | 0 | 0.000 [0.000, 0.278] | 1 |
| sample3_atom | 15 | 14 | 2 | 0.143 [0.040, 0.399] | 1 |

The gold stage column is the number of traces with a gold stage (13, 11, 15 after amendment 1); the both-stages column is one fewer per sample because one trace has no proxy stage. The agreement denominator is the both-stages column.

## Confusion, proxy stage (rows) by gold stage (columns)

### sample1_uniform

| proxy \ gold | extraction | transmission | aggregation |
| --- | ---: | ---: | ---: |
| extraction | 0 | 0 | 0 |
| transmission | 2 | 0 | 1 |
| aggregation | 8 | 0 | 1 |

### sample2_coarse

| proxy \ gold | extraction | transmission | aggregation |
| --- | ---: | ---: | ---: |
| extraction | 0 | 0 | 0 |
| transmission | 0 | 0 | 1 |
| aggregation | 9 | 0 | 0 |

### sample3_atom

| proxy \ gold | extraction | transmission | aggregation |
| --- | ---: | ---: | ---: |
| extraction | 0 | 0 | 0 |
| transmission | 3 | 0 | 1 |
| aggregation | 8 | 0 | 2 |

## Checks and caveats

The proxy stage path reproduces the stored `random_relay` distribution: yes.

The same labeller labels both fact sets at the same checkpoints, so shared labeller error inflates the rate. Samples 2 and 3 draw traces by a lexical-loss filter and share their 30 traces.

## Fix attempt: proxy presence re-derived at atom level

`Proxy-atom-presence.md` (sha `3f46ca1d...`), Haiku 5.5 with the validated point prompt on the Qwen proxy facts,
all 31 unique random_relay traces, $0.028124, cap $0.30. Every fact/checkpoint validated. Full report and confusion
tables: `../20261115_proxy_atom_presence/report.md`.

| sample | both stages | agree | rate [95% Wilson] | proxy stage source |
| --- | ---: | ---: | --- | --- |
| sample1_uniform | 12 | 1 | 0.083 [0.015, 0.354] | stored checkpoint labels |
| sample1_uniform | 13 | 3 | 0.231 [0.082, 0.503] | atom-level point labeller |
| sample2_coarse | 10 | 0 | 0.000 [0.000, 0.278] | stored checkpoint labels |
| sample2_coarse | 11 | 2 | 0.182 [0.051, 0.477] | atom-level point labeller |
| sample3_atom | 14 | 2 | 0.143 [0.040, 0.399] | stored checkpoint labels |
| sample3_atom | 15 | 4 | 0.267 [0.109, 0.520] | atom-level point labeller |

The atom-level derivation moves the rate up but stays low, and the confusion stays one-directional: the proxy stage
is aggregation in 9 of 13, 9 of 11 and 10 of 15 traces while the gold stage is extraction in 10 of 13, 9 of 11 and
11 of 15. Re-deriving proxy presence at the labeller's own atom unit does not make the two audits agree.

Causes of the disagreements in the atom-level comparison, one per trace, are in `diagnosis.md`.