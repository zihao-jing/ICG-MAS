# E3 pilot rule: checkpoint-removal route counts (frozen before the run)

Date: 2026-11-14. Pilot only; 50 traces. No model calls: the replay reads the
frozen per-fact labels in `rebuttal/pilots/20261113_main_table_redo/results.json`
(MuSiQue, score-ranked relay, three paper models, k = 1). Cost $0.00.

## Population

2,400 traces (800 MuSiQue instances x 3 models). Each trace has one extraction
row and one board row with the same fact ids. The pilot takes the first 50 by
ascending SHA-256 of canonical JSON `["E3-pilot", 43, model, instance_id]`.

## Route rule (full audit)

Applied in this order:
1. **extraction** if any fact has `status == absent` at the extraction checkpoint;
2. **selection** if extraction is complete but any fact is `absent` at the board;
3. **distortion** if the board is complete and any carried fact has
   `fidelity == distorted` (strict; `partial` is its own group, not distortion);
4. **aggregation** if the board is complete and faithful and `answer_correct`
   is false;
5. otherwise **correct**.

## Removals

- `pool`: ignore the extraction check (step 1).
- `fidelity`: treat `distorted` as faithful (step 3).
- `aggregation`: do not route a wrong answer with complete faithful coverage
  (step 4).
- all three: every trace is **unrouted**.

A route change is a trace whose route under the removal differs from the full
route. Reported: n, changed n and share, Wilson 95% CI, and the full -> new
route pairs, by model. Descriptive only; no test.

## Outputs

`rebuttal/pilots/20261114_e3_pilot/`: `population.json`, `results.json`,
`report.md`, `run_identity.json` (rule and population hashes).