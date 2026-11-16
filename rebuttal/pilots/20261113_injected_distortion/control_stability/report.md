# Faithful-rewrite control: stability rerun (item 5)

Rule `CONTROL_TIGHTENING.md` (sha256 `a547ea2c2b6e`), frozen before the calls. 7 cases, one base_repeat call each; spend $0.000767, cap $5.00.

| case | model | gold | base_repeat | control | base | reading |
| --- | --- | --- | --- | --- | --- | --- |
| 2hop__316374_82341 | gpt4omini | in Northern Florida | wrong | wrong | exact | answer-equivalent |
| 2hop__814671_82341 | qwen235b | in Northern Florida | wrong | wrong | exact | answer-equivalent |
| 2hop__95172_152907 | gpt4omini | La Goulette | wrong | wrong | exact | aggregation instability |
| 3hop1__144439_443779_52195 | qwen235b | Francisco Guterres | exact | wrong | exact | rewrite-induced |
| 3hop1__17192_78396_157843 | gpt4omini | 1853 | exact | wrong | exact | rewrite-induced |
| 3hop1__254856_400692_51423 | gemma31b | Casa Loma | wrong | wrong | exact | aggregation instability |
| 4hop1__429751_32392_823060_610794 | gemma31b | Richland County | wrong | wrong | exact | aggregation instability |

## Reading

Of the 7 control failures, **2** are answer-equivalent exact misses ("in Northern Florida" vs "Northern Florida"), **2** are rewrite-induced (base_repeat exact, control wrong), and **3** are aggregation instability (the same original board, re-asked, is also wrong). The tightened denominator is 30 minus the unstable cases: **2/27** (7.4%, 95% CI 0.9-24.3). The original 7/30 stays on record. The two rewrite-induced cases are a wrong number (1853 -> 1886) and an empty output; neither removes the critical fact from the board.

