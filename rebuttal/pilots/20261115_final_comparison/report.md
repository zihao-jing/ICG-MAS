# Final comparison on the 89 known-stage cases

2026-11-15. Population: 89 cases with a known stage — 30 injected (truth transmission, by construction) and
59 missing-fact cohort cases (39 extraction, 20 sharding). Every cell is accuracy against the known stage;
intervals are Wilson 95%.

| method | backbone | injected (n=30) | missing-fact (n=59) | all (n=89) |
| --- | --- | ---: | ---: | ---: |
| Evidence-flow audit | Gemini 3.6 Flash carrier labeller | 21/30 = .700 [.521, .833] | 45/59 = .763 [.640, .853] | **66/89 = .742 [.642, .821]** |
| Evidence-flow audit | Qwen-235B carrier labeller | 27/30 = .900 [.744, .965] | 37/59 = .627 [.500, .739] | **64/89 = .719 [.618, .802]** |
| Who&When-style judge | Gemini 3.6 Flash | 24/30 = .800 [.627, .905] | 43/59 = .729 [.604, .826] | **67/89 = .753 [.654, .831]** |
| Who&When-style judge | Qwen-235B | 27/30 = .900 [.744, .965] | 29/59 = .492 [.368, .616] | **56/89 = .629 [.525, .722]** |
| [R1] re-implementation | Gemini 3.6 Flash | 27/30 = .900 [.744, .965] | 26/59 = .441 [.322, .567] | **53/89 = .596 [.492, .691]** |
| [R1] re-implementation | Qwen-235B | 25/30 = .833 [.664, .927] | 37/59 = .627 [.500, .739] | **62/89 = .697 [.595, .782]** |
| Lexical checkpoint-drop baseline | model-free rule | 0/30 = .000 [.000, .114] | 39/59 = .661 [.534, .769] | 39/89 = .438 [.340, .542] |

The lexical row is a fixed rule, so it is the same in both backbone columns and is listed once.

Notes that belong with the table:

- The audit rows carry the statement-based shard-presence rule (`Sharding-presence-semantic-v1.md`, sha
  `b9eb130f…`), the third rule on these 89 cases; the gain it brings is post-hoc. The two unscored Gemini
  cases (`inj/gpt4omini/4hop1__93963_170667_443779_52195`, `inj/gemma31b/4hop1__151903_5274_458768_33677`)
  are counted wrong in the 66/89, as in the old 61/89.
- The audit rows label fixed Qwen-generated facts; only the carrier labeller is swapped. The judge and [R1]
  rows regenerate from the trace with the model named.
- The injected row is the independent test. The missing-fact row shares the audit's input-presence check with
  the cohort truth, so it is a consistency check for the audit rows; the judge and [R1] do not use that check.
- [R1] uses its released prompt and parser unchanged and reads the stage from the released step coordinate
  under the frozen map `R1-coordinate-stage-map.md` (sha `2015e084…`); the mode-code map is withdrawn.

## Source file for each cell

| cell | source |
| --- | --- |
| audit, Gemini (new rule) | `rebuttal/pilots/20261115_sharding_semantic/canonical.json` (old stages from `20261115_b5_attribution_2x2/audit_a_gemini.json`, rescored on `20261115_sharding_semantic/results.jsonl`) |
| audit, Qwen (new rule) | `rebuttal/pilots/20261115_sharding_semantic/canonical.json` (old stages from `20261115_b5_qwen_design_a/results.json`, rescored on the same labels) |
| judge, Gemini | `rebuttal/pilots/20261113_attribution_comparison/results_v2.json`, field `judge.stage` |
| judge, Qwen | `rebuttal/pilots/20261115_b5_attribution_2x2/judge_qwen.json` |
| [R1], Gemini | `rebuttal/pilots/20261115_r1_full/rescore_coordinate.json` (the mode-map `score.json` is withdrawn) |
| [R1], Qwen | `rebuttal/pilots/20261115_r1_qwen/score.json` |
| lexical | `rebuttal/pilots/20261113_attribution_comparison/report.md`, recomputed by `scripts/attribution_comparison_v2.py` |

Run costs: [R1] Gemini $0.870774 (89 calls); [R1] Qwen $0.034209 (89 calls, projection $0.0671, cap $1).
The judge and audit cell costs are in their own pilot folders.

## Movement under the new shard rule

Of the 15 Gemini sharding-known cases the old rule called extraction, 8 now take sharding and 7 stay
extraction. Of the 9 Qwen cases, 7 move and 2 stay. Correct cases that break: 5 on Gemini, 1 on Qwen. Wrong
cases that become correct: 10 on Gemini, 8 on Qwen. Repair-arm membership moves 12 in / 3 out (Gemini) and
8 in / 1 out (Qwen); the 0/6 supported-repair result stands for the old arm, and the newly routed cases are
untested.

## Not in this table

The pooled Silo-Bench extraction run is still writing; its pooled figure is reported separately when it ends.