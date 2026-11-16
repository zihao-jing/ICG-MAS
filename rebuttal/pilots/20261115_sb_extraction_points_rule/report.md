# Silo-Bench extraction re-score under the validated point unit

2026-11-15. Prompt `per_fact_points_prompt_v1.json` (sha `86d84ff6…`), unit from
`Per-fact-presence-points-v1.md` via `scripts.per_fact_points_build.atomize` (list elements, dict keys,
sentences). Labeller Claude Haiku 5.5, temperature 0, one call per (trace, support), 8,192-token cap. Population:
the 51 qwen235b random_relay Silo-Bench traces in E3, 380 gold supports.

## Result

| quantity | value |
| --- | ---: |
| traces | 51 |
| supports | 380 |
| atoms | 6,821 |
| atom presence (present atoms / all atoms) | **.737** |
| support present (all atoms present) | .679 |
| support partial | .242 |
| trace mean atom critical recall | .758 |
| invalid labels | 0 |

By kind: list supports (320, 6,701 atoms) .737 atom presence; dict supports (30, 90 atoms) .689; single
supports (30) 1.000.

Spend **$0.395763**, cap $2.00. All 380 calls completed and parsed.

## The first re-score is on record and not used

`20261115_sb_extraction_points/` split supports on sentence boundaries only, so 350 of 380 supports (the lists
and dicts) were labelled as a single atom each: 380 atoms, atom presence .676, $0.162332. That unit is not the
one the label was validated on (atom κ .847), so its figures do not inherit the validation and are not citable.
Two runs, total $0.558095 of the $6.00 step cap.

## What this does and does not support

It is one cell: qwen235b, random_relay, extraction checkpoint, 51 traces. The Silo-Bench row in the CR8J W2
response is pooled over 208 traces at the board checkpoint, so this figure neither replaces nor restores it. As
an extraction-checkpoint figure it is much lower than the MuSiQue extraction CR (.912), which is consistent with
list-heavy Silo-Bench facts being only partly carried even when an entry exists.