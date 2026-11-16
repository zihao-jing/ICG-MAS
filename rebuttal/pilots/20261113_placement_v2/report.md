# Delivery diagnostic v2 — oracle corrective unit

Amendment `PLACEMENT_AMENDMENT_V2.md` (sha256 `4dd32be88dd6`); action manifest `597b58afedcc`. Spend $0.006502.

The v1 run and its all-wrong result stay on record in `../20261113_placement/report.md`. Diagnosis: the v1 inserted line was the agent's raw input shard, and it contained the stored gold answer in **0 of 6** piloted traces. v2 inserts an oracle evidence statement that contains the gold in **6 of 6**, identical in both arms. **Both arms therefore receive the decisive evidence, so this run cannot test whether placement brings missing evidence to the model.** It tests only whether a sufficient corrective unit is used at the final answer, and whether its position changes that use. The target-vs-hash difference is not a placement effect.

| trace | model | base | target agent | hash agent | target | hash |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| III-28_n10::seed43 | google | no | 0 | 2 | no | no |
| III-27_n10::seed43 | google | no | 0 | 4 | yes | yes |
| II-13_n10::seed43 | openai | no | 0 | 5 | yes | yes |
| III-27_n10::seed43 | openai | no | 9 | 7 | no | no |
| II-17_n10::seed43 | qwen | no | 0 | 3 | no | yes |
| III-28_n10::seed43 | qwen | no | 2 | 6 | no | no |

Target exact **2/6** (33.3%, 95% CI 4.3-77.7%); hash exact **3/6** (50.0%, 95% CI 11.8-88.2%); paired difference -1 at n=6 (**descriptive only**; this is a 6-trace pilot, not a population claim).

Inserted text (identical in both arms):

- III-28_n10::seed43 / google: `Corrected evidence from this agent's partition: the result is {'0': 0.008958, '1': 0.017813, '2': 0.010198, '3': 0.001875, '4': 0.016042, '5': 0.019583, '6': 0.`
- III-27_n10::seed43 / google: `Corrected evidence from this agent's partition: the result is [[28, 28, 2.5622], [7, 28, 2.5064], [11, 28, 2.4863]].`
- II-13_n10::seed43 / openai: `Corrected evidence from this agent's partition: the result is 7.`
- III-27_n10::seed43 / openai: `Corrected evidence from this agent's partition: the result is [[28, 28, 2.5622], [7, 28, 2.5064], [11, 28, 2.4863]].`
- II-17_n10::seed43 / qwen: `Corrected evidence from this agent's partition: the result is [23, -4, -31, 34, 42, -72, 35, -11, 68, -11, -18, -68, 15, 8, 66, -50, 57, -58, -27, 35, 23, -21, `
- III-28_n10::seed43 / qwen: `Corrected evidence from this agent's partition: the result is {'0': 0.008958, '1': 0.017813, '2': 0.010198, '3': 0.001875, '4': 0.016042, '5': 0.019583, '6': 0.`

## Reading

The oracle unit is used in **5/12** arm calls (target 2, hash 3), against **0/12** in v1, consistent with the v1 failure being delivery: its raw shard never contained the missing evidence. The arms disagree on 1 of 6 traces. On III-28 (google) both arms return the same full vector, so neither call used the corrective unit; on II-17 (qwen) the hash arm returns the correct array while the target arm emits a degenerate repeated "the" string. With n=6 the target-vs-hash difference is not a placement effect; the pilot shows the aggregator uses an explicit corrective unit in some calls, not that placement delivers the evidence.
