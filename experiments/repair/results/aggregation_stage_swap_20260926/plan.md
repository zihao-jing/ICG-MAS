# Full aggregation comparison with one Gemini middle call per case

The cohort contains all 326 revised `aggregation_gap` cases from the previous improvement table, across three baselines and nine settings. The archived Gemini-terminal arm already has one Gemini call per case on the frozen original board.

In the new middle arm, choose one agent deterministically from the case key (SHA-256, seed 42). Ask Gemini to extract up to three atomic units from only that agent’s original shard. Replace that agent’s units on the frozen board, leave every other agent’s units and the final aggregation prompt unchanged, then ask the original baseline model to aggregate. This is one Gemini call plus one original-model call per case. The original protocol transmits all extracted units because its cap is three, so rescoring cannot change which units are transmitted; the new units retain extraction order.

| Setting | N | Original mean score | Existing Gemini terminal mean | New calls |
| --- | ---: | ---: | ---: | ---: |
| gemma31b_musique | 74 | 0.124 | 0.184 | 148 |
| gemma31b_silobench_n5 | 15 | 0.000 | 0.200 | 30 |
| gemma31b_silobench_n10 | 17 | 0.000 | 0.059 | 34 |
| gpt4omini_musique | 71 | 0.134 | 0.324 | 142 |
| gpt4omini_silobench_n5 | 22 | 0.000 | 0.409 | 44 |
| gpt4omini_silobench_n10 | 22 | 0.000 | 0.136 | 44 |
| qwen235b_musique | 68 | 0.216 | 0.347 | 136 |
| qwen235b_silobench_n5 | 19 | 0.000 | 0.368 | 38 |
| qwen235b_silobench_n10 | 18 | 0.000 | 0.111 | 36 |

**Total:** 326 cases and 652 new calls: 326 Gemini extraction calls and 326 original-model aggregation calls. The terminal arm is already saved and its prompt hash matches each frozen manifest.

The two upgraded model placements have the same number of Gemini calls, but different information scope: the selected middle agent sees one shard; the terminal model sees the complete board. Report this asymmetry explicitly. Report whether each new board retains answer-critical evidence before attributing a result to aggregation. The 14 reclassified cases had source-to-board review; the other 312 retain a coarse audit diagnosis.

The `cohort.csv` file freezes every case, selected agent, saved original result, archived Gemini-terminal result, and prompt hash. `plan.json` gives calls by setting. The run is complete; see [`summary.md`](summary.md) for the outcomes.
