# Matched placement test (item 7)

Rule `PLACEMENT_MATCHED.md` (sha256 `37354495cad4`), frozen before the calls. Stronger model `google/gemini-3.6-flash`; 30/30 injected cases; spend $0.109805, cap $5.00. Stage: relay checkpoint; aggregation held at the original model and prompt.

| case | model | diagnosed agent | random agent | diagnosed | random |
| --- | --- | ---: | ---: | --- | --- |
| 2hop__15416_58040 | gpt4omini | 0 | 1 | wrong | wrong |
| 2hop__17455_21567 | gpt4omini | 0 | 1 | exact | wrong |
| 2hop__316374_82341 | gpt4omini | 1 | 0 | wrong | wrong |
| 2hop__373544_66723 | gemma31b | 0 | 1 | wrong | wrong |
| 2hop__446324_620302 | qwen235b | 1 | 0 | wrong | wrong |
| 2hop__51074_75184 | gemma31b | 0 | 1 | exact | wrong |
| 2hop__6827_86319 | gemma31b | 0 | 1 | wrong | wrong |
| 2hop__734582_71302 | gpt4omini | 1 | 0 | wrong | wrong |
| 2hop__739909_807845 | gpt4omini | 1 | 0 | wrong | wrong |
| 2hop__804417_126089 | gpt4omini | 1 | 0 | wrong | wrong |
| 2hop__814671_82341 | qwen235b | 1 | 0 | wrong | wrong |
| 2hop__835710_7298 | qwen235b | 0 | 1 | wrong | wrong |
| 2hop__84847_21969 | gpt4omini | 1 | 0 | wrong | wrong |
| 2hop__95172_152907 | gpt4omini | 0 | 1 | wrong | wrong |
| 3hop1__144439_443779_52195 | qwen235b | 1 | 0 | exact | wrong |
| 3hop1__17192_78396_157843 | gpt4omini | 2 | 0 | exact | wrong |
| 3hop1__254856_400692_51423 | gemma31b | 0 | 1 | wrong | wrong |
| 3hop1__275261_443779_52195 | gemma31b | 2 | 0 | wrong | wrong |
| 3hop1__488744_443779_52195 | gpt4omini | 2 | 0 | exact | wrong |
| 3hop1__488744_443779_52195 | gemma31b | 2 | 0 | wrong | wrong |
| 3hop1__5544_34179_23375 | gpt4omini | 1 | 0 | exact | wrong |
| 3hop1__617062_127905_80286 | gemma31b | 1 | 0 | wrong | wrong |
| 3hop1__64694_34179_23375 | qwen235b | 1 | 0 | wrong | wrong |
| 3hop1__742780_567566_84283 | gemma31b | 2 | 0 | wrong | wrong |
| 3hop1__773623_87694_124169 | qwen235b | 0 | 1 | wrong | wrong |
| 3hop1__773623_87694_124169 | gpt4omini | 0 | 1 | wrong | wrong |
| 4hop1__151903_5274_458768_33677 | gemma31b | 1 | 0 | wrong | wrong |
| 4hop1__429751_32392_823060_610794 | gemma31b | 1 | 0 | exact | wrong |
| 4hop1__606685_508773_85832_745702 | gemma31b | 0 | 1 | wrong | wrong |
| 4hop1__93963_170667_443779_52195 | gpt4omini | 1 | 0 | exact | wrong |

Diagnosed exact **8/30** (26.7%, 95% CI 12.3-45.9); random exact **0/30** (0.0%). Paired difference +8 at n=30; descriptive only.

## Reading

Both arms replace the same corrupted unit at the same position, so both remove the injected corruption; only the agent whose shard the stronger model reads changes. This is the matched contrast the earlier 11/30 versus 0/30 result lacked. A difference here is a placement signal for this one replaced unit, not a full repair and not a claim about other pipeline stages.
