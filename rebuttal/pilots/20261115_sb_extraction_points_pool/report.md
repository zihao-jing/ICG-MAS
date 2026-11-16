# Silo-Bench extraction checkpoint, pooled — relay-only figure

2026-11-15. Labeller: Claude Haiku 5.5, point-level prompt `prereg/per_fact_points_prompt_v1.json` (sha `86d84ff6…`),
the unit the label was validated on. Validation: atom κ .847 [.690, .967] against a Gemini reference
(`20261115_sb_points/report.md`). Spend for this run $1.056 of the $3.00 cap. Scores: `score.json` (same folder).

## Population

Relay traces only: `random_relay`, `score_ranked_relay` and `redundancy_aware_relay`, each at n = 5 and n = 10
agents (six cells) of the Silo-Bench main table. Summary-exchange traces are not in this row: they have no
per-agent extraction units, so the extraction checkpoint does not exist for them.

## Result

| Population | Traces | Supports | Support present [95% CI] | Atom present [95% CI] |
| --- | ---: | ---: | --- | --- |
| Relay traces (`random_relay`, `score_ranked_relay`, `redundancy_aware_relay`) | 156 | 1,170 | .687 [.660, .713] | .746 [.741, .752] (21,213 atoms) |

Wilson 95%. Atom presence counts the labelled atoms of the relay supports; the support column counts supports with every atom present.

## The 208-trace figure is not usable

`score.json` pools all 208 traces (1,560 supports): support present .515, atom present .560. It includes the 52
summary-exchange traces. Their extraction pool is empty, so the labeller received no evidence and labelled every atom
`absent` (atom presence 0.000 in both n = 5 and n = 10 summary cells). That is an input artifact, not a measurement.
The pooled figure is therefore excluded from the text.

## Sources

- Labels: `results.jsonl` (1,180 new supports) and `20261115_sb_extraction_points_rule/` (380 prior supports, reused at $0).
- Scores: `score.json` (all 208 traces, per-cell breakdown); the relay-only figures are computed from the same records
  with the summary-exchange keys removed.
- Validation: `20261115_sb_points/report.md`, atom κ .847 [.690, .967].
