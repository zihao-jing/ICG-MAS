# Placement by redoing the blamed relay step (item 7, pilot)

Rule `PLACEMENT_REDO_RULE.md` (sha256 `da8667039714`), frozen before the calls. Stronger model `google/gemini-3.6-flash`; pilot 10/30 injected cases; spend $0.059244, cap $5.00. Stage: relay checkpoint; aggregation held at the original model and prompt.

| case | model | diagnosed agent | random agent | diagnosed | random |
| --- | --- | ---: | ---: | --- | --- |
| 2hop__15416_58040 | gpt4omini | 0 | 1 | exact | wrong |
| 2hop__6827_86319 | gemma31b | 0 | 1 | wrong | wrong |
| 2hop__734582_71302 | gpt4omini | 1 | 0 | wrong | wrong |
| 2hop__739909_807845 | gpt4omini | 1 | 0 | wrong | wrong |
| 2hop__804417_126089 | gpt4omini | 1 | 0 | wrong | wrong |
| 2hop__835710_7298 | qwen235b | 0 | 1 | wrong | wrong |
| 2hop__84847_21969 | gpt4omini | 1 | 0 | exact | wrong |
| 3hop1__254856_400692_51423 | gemma31b | 0 | 1 | wrong | wrong |
| 3hop1__773623_87694_124169 | qwen235b | 0 | 1 | wrong | wrong |
| 4hop1__606685_508773_85832_745702 | gemma31b | 0 | 1 | wrong | wrong |

Diagnosed arm exact **2/10** (20.0%, 95% CI 2.5-55.6); random arm **0/10** (0.0%). Paired difference +2 at n=10; descriptive only.

## Reading

Both arms replace one board unit with a stronger-model transmission from that agent's own shard; only the agent changes. The diagnosed arm is the stage the audit blames. A difference in exact answers is a placement signal, not a full repair: the aggregation model and the rest of the board are unchanged, and n=10 is a pilot. Two earlier configurations are kept on record and are not scored: `results_pre_corruptfix.json` (the corruption was not applied to the board) and `results_reasoning_disabled.json` (Gemini rejected with 400 because reasoning was disabled).
