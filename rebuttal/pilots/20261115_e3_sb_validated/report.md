# E3 on Silo-Bench from the validated labels (relay protocols)

2026-11-15. $0, no model calls. Script `scripts/e3_sb_validated.py`; numbers in `e3.json` (same folder).
Replaces the exploratory E3 labels of `20261114_e3_sb/` (not reused). Wilson 95% intervals.

## Labels used

- Extraction checkpoint: point-level prompt `per_fact_points_prompt_v1.json`, validated on Silo-Bench at atom
  kappa .847 [.690, .967] against a Gemini 3.6 Flash reference (`20261115_sb_points/report.md`).
- Board checkpoint: per-fact presence prompt `labeller_prompt.json`, validated on Silo-Bench at agreement .915 and
  kappa .653 [.447, .854] on 515 facts (`20261113_sb_presence_validation/report_v2.md`). The board kappa is wide;
  read the board rate with that in mind.

## Population

Relay protocols only: `random_relay`, `score_ranked_relay`, `redundancy_aware_relay`. Summary exchange excluded
at both checkpoints (its extraction pool is empty; see `20261115_sb_extraction_points_pool/report.md`).

- Extraction: 156 traces, all qwen235b (3 protocols x 52 instances), 1,170 supports, 21,213 atoms.
- Board, qwen235b only: the same 156 traces, 1,170 facts. Board, all three models: 468 traces, 3,490 labelled facts.

## Result

| Checkpoint | Unit | Population | Rate [95% Wilson] |
| --- | --- | --- | --- |
| Extraction | support, all atoms present | qwen235b, 1,170 supports | .687 [.660, .713] |
| Extraction | atom, present | qwen235b, 21,213 atoms | .746 [.741, .752] |
| Board | fact, present | qwen235b, 1,170 facts | .767 [.742, .790] |
| Board | fact, present | three models, 3,490 facts | .866 [.854, .877] |

Board by agent count, qwen235b: n = 5 .810 [.768, .846] (390 facts); n = 10 .745 [.713, .774] (780 facts).
Partial counts as not present in both checkpoints.

## Caveat

The extraction and board units differ: extraction is per support (and per atom); board is per fact. The
extraction support rate is the stricter unit, so the two rates are not a like-for-like gap. The board kappa lower
bound is .447, so the board rate has an interval that the label itself does not pin down.

## Sources

- `rebuttal/pilots/20261115_sb_extraction_points_pool/results.jsonl` (relay rows) and
  `rebuttal/pilots/20261115_sb_extraction_points_rule/results.jsonl` (relay rows, 380 supports reused at $0).
- `rebuttal/pilots/20261113_sb_presence_full/results.json` (checkpoint board; prompt sha `27aca1cc`).
- Validation: `20261115_sb_points/report.md`, `20261113_sb_presence_validation/report_v2.md`.
