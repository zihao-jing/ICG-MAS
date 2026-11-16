# E1 pre-registration v3 — planned, pending author confirmation

Date: 2026-11-08. This is a complete proposed design before human labelling, not a frozen matcher or authorisation to enlarge the sample. The current budget remains 60 held-out instances. The 80/100-instance lists below are proposed alternatives only. No held-out labels or matcher outcomes enter selection. Old technical pilot ledgers retain their original immutable preregistration files/hashes.

## Estimands and decision rules

Report human–human Cohen κ and matcher accuracy against adjudicated human labels as estimates with 95% CIs. There is no threshold-based acceptance rule. Plan A makes fact-level presence and fidelity primary. All three base models and k=3 are included; k=1/3 full matcher re-estimation is a separate subsequent workload, not extra held-out annotation.

Presence is whether a source-grounded carrier of a specified atomic fact exists at the checkpoint, allowing a partial/distorted carrier to be present but not faithful. Joint carriers are evaluated together; independent alternatives are separate carriers. Fidelity is faithful / partial / distorted for each adjudicated-present atomic fact: faithful if at least one sole/alternative or complete joint carrier is faithful; otherwise partial if a noncontradictory partial carrier exists; otherwise distorted if only contradictory carriers exist. Uncertain alternatives that could change this call yield uncertain. This aggregation rule is fixed before labels; all carrier-group labels remain secondary detail. Missing machine carriers count as wrong, not excluded. Uncertain human presence/fidelity is adjudicated where possible, otherwise counted separately and excluded with denominators reported. Report board and extraction separately; board is the primary checkpoint. Each atomic fact receives its instance's inverse-probability weight. Presence uses all specified facts; fidelity uses adjudicated-present facts, one row per fact; do not pool these denominators.

Secondary outputs, always reported: human κ and matcher accuracy for wrong traces classified lost vs reached-but-unused; and weighted candidate-aggregation-failure rates from human labels for MuSiQue and Silo-Bench. The named script outputs are `MQ_candidate_aggregation_failure_rate_human` and `SB_candidate_aggregation_failure_rate_human`. These answer the CR8J 68% headline directly: denominator ALL traces (including correct), numerator wrong traces with a human-validated faithfully complete sufficient support set on the board. Report pooled and per-base-model rates. Trace decision follows the fewest non-present facts sufficient-set rule, sorted fact-ID tie-break, with extraction omission before selection omission before strict distortion. A faithfully complete wrong trace is reached-but-unused. No repair outcome serves as reference.

Primary binary analysis excludes human `partial` and `uncertain` traces and reports both counts separately. Pre-registered sensitivity counts `partial` as `lost`, still excludes `uncertain`, and keeps machine failures as errors. Show both estimates/CIs and their difference; explicitly describe changed direction or interpretation in plain words, never select the favourable result. This sensitivity is planned, pending author confirmation. The candidate-aggregation rate retains partial/uncertain in its all-trace denominator; partial cannot be counted as faithfully complete, while an unresolved-case upper-bound sensitivity treats uncertain wrong traces as possible candidate aggregation failures.

## Lexical sampling frame and draw

Population: the 152 cached final-evaluation instances (100 MuSiQue, 52 Silo-Bench), excluding the 20 already fixed dev instances from held-out selection, leaving 85 MQ and 47 SB. Pilot/calibration IDs remain outside this population. For unbiased full-frame candidate-aggregation rates, include all 20 human-labelled dev instances as certainty units (π=1,w=1); they are excluded from held-out matcher-validation statistics. Without those labels, the script refuses to present the full-frame headline rate.

Strata use ONLY benchmark and cached Qwen k=3 lexical coverage at τ=0.5: zero (CR=0), partial-coverage (0<CR<1), complete (CR=1). “Partial-coverage” is a lexical stratum, not the semantic fidelity label partial. The existing `scripts/exp_rebuttal_threshold.py` similarity is used unchanged (maximum number-overlap/Jaccard, strict similarity >0.5). Neither correctness nor matcher output defines strata or selects IDs. Correctness is used only to model the workload for the secondary wrong-trace statistic.

Allocate 75% MQ /25% SB. Within each benchmark, cycle nonempty strata in sorted order, equally allocating one position at a time, capping a stratum at its population size. Order IDs within each stratum by ascending SHA-256 of canonical JSON `["E1-lexical-v3",42,stratum,instance_id]`, then ID on ties. Seed 42 was fixed before labels. A sampled instance's inclusion probability is π_h=n_h/N_h and its weight is w_i=1/π_h=N_h/n_h. All model traces, facts and carrier groups from that instance inherit this weight. The deterministic hash is the reproducible random ordering; probabilities refer to the seeded random-order sampling design, not model outcomes.

Weighted κ uses weighted observed and chance agreement from the two human marginals. Accuracy is weighted correct / weighted eligible; failed machine traces/facts remain errors. Resample whole instance IDs within lexical strata, jointly retaining all models/facts and fixed design weights, 2,000 draws, seed 42, percentile 95% CI. Report undefined κ and valid-draw count; do not impute it. No finite-population correction is used for validation, conservatively. For full-frame rates, observed dev certainty units remain fixed during bootstrap; report that these intervals do not model residual adjudication uncertainty. Full-population model errors are not conflated with annotation uncertainty.

## Fixed proposed lists and weights

### Held-out N=60 (planned only)

| Stratum | N_h | n_h | π_h | w_i |
|---|---:|---:|---:|---:|
| MQ/complete | 4 | 4 | 1.000000000000 | 1.000000000000 |
| MQ/partial | 44 | 21 | 0.477272727273 | 2.095238095238 |
| MQ/zero | 37 | 20 | 0.540540540541 | 1.850000000000 |
| SB/complete | 26 | 5 | 0.192307692308 | 5.200000000000 |
| SB/partial | 15 | 5 | 0.333333333333 | 3.000000000000 |
| SB/zero | 6 | 5 | 0.833333333333 | 1.200000000000 |

MQ/complete:
```json
["2hop__363216_787353", "3hop1__103254_214799_259594", "2hop__70338_36240", "2hop__488811_30113"]
```

MQ/partial:
```json
["4hop1__802394_153080_33897_81096", "3hop1__465684_160545_62931", "3hop1__106042_64399_59680", "2hop__525581_161450", "4hop1__47210_53706_795904_580996", "2hop__135822_46621", "2hop__677929_696450", "3hop1__147225_30587_83479", "4hop1__814349_624859_355213_203322", "3hop1__53690_161697_73916", "3hop2__72083_92991_76291", "2hop__119423_779396", "2hop__450600_158262", "2hop__640262_122868", "2hop__511454_120259", "4hop1__726675_508773_85832_745702", "3hop1__786067_228453_86925", "3hop2__304722_590317_63959", "2hop__415518_616002", "4hop3__152056_698586_91248_54362", "2hop__17192_77606"]
```

MQ/zero:
```json
["2hop__631139_75487", "3hop2__132957_433432_40768", "2hop__28287_89399", "2hop__846844_47134", "2hop__525242_52835", "2hop__486314_544665", "2hop__142621_225454", "2hop__458672_20057", "3hop1__640171_228453_86925", "3hop2__132957_51933_40768", "2hop__81659_52835", "3hop2__106842_30645_84681", "2hop__71755_463572", "2hop__284789_52835", "2hop__121386_37168", "2hop__31085_23241", "3hop1__133292_40769_64047", "2hop__433694_20273", "3hop1__389955_132457_47686", "3hop2__20335_8533_9331"]
```

SB/complete:
```json
["III-30_n10", "I-08_n5", "I-09_n10", "I-05_n5", "II-17_n10"]
```

SB/partial:
```json
["III-29_n5", "III-27_n5", "III-24_n5", "III-23_n10", "I-10_n10"]
```

SB/zero:
```json
["II-13_n10", "I-02_n5", "I-03_n5", "I-02_n10", "II-15_n5"]
```
### Held-out N=80 (planned only)

| Stratum | N_h | n_h | π_h | w_i |
|---|---:|---:|---:|---:|
| MQ/complete | 4 | 4 | 1.000000000000 | 1.000000000000 |
| MQ/partial | 44 | 28 | 0.636363636364 | 1.571428571429 |
| MQ/zero | 37 | 28 | 0.756756756757 | 1.321428571429 |
| SB/complete | 26 | 7 | 0.269230769231 | 3.714285714286 |
| SB/partial | 15 | 7 | 0.466666666667 | 2.142857142857 |
| SB/zero | 6 | 6 | 1.000000000000 | 1.000000000000 |

MQ/complete:
```json
["2hop__363216_787353", "3hop1__103254_214799_259594", "2hop__70338_36240", "2hop__488811_30113"]
```

MQ/partial:
```json
["4hop1__802394_153080_33897_81096", "3hop1__465684_160545_62931", "3hop1__106042_64399_59680", "2hop__525581_161450", "4hop1__47210_53706_795904_580996", "2hop__135822_46621", "2hop__677929_696450", "3hop1__147225_30587_83479", "4hop1__814349_624859_355213_203322", "3hop1__53690_161697_73916", "3hop2__72083_92991_76291", "2hop__119423_779396", "2hop__450600_158262", "2hop__640262_122868", "2hop__511454_120259", "4hop1__726675_508773_85832_745702", "3hop1__786067_228453_86925", "3hop2__304722_590317_63959", "2hop__415518_616002", "4hop3__152056_698586_91248_54362", "2hop__17192_77606", "3hop2__92991_28727_76291", "3hop1__64957_87694_64412", "3hop1__132795_40769_64047", "3hop1__791757_15840_36002", "2hop__203437_152093", "4hop1__72247_497223_15840_36014", "2hop__161273_92673"]
```

MQ/zero:
```json
["2hop__631139_75487", "3hop2__132957_433432_40768", "2hop__28287_89399", "2hop__846844_47134", "2hop__525242_52835", "2hop__486314_544665", "2hop__142621_225454", "2hop__458672_20057", "3hop1__640171_228453_86925", "3hop2__132957_51933_40768", "2hop__81659_52835", "3hop2__106842_30645_84681", "2hop__71755_463572", "2hop__284789_52835", "2hop__121386_37168", "2hop__31085_23241", "3hop1__133292_40769_64047", "2hop__433694_20273", "3hop1__389955_132457_47686", "3hop2__20335_8533_9331", "3hop1__389955_132457_51423", "2hop__280583_229757", "2hop__491195_265959", "2hop__307218_161450", "3hop1__41865_55331_34700", "2hop__6956_192417", "3hop1__131820_59747_48534", "2hop__60001_512508"]
```

SB/complete:
```json
["III-30_n10", "I-08_n5", "I-09_n10", "I-05_n5", "II-17_n10", "III-23_n5", "III-26_n5"]
```

SB/partial:
```json
["III-29_n5", "III-27_n5", "III-24_n5", "III-23_n10", "I-10_n10", "II-18_n10", "II-18_n5"]
```

SB/zero:
```json
["II-13_n10", "I-02_n5", "I-03_n5", "I-02_n10", "II-15_n5", "I-03_n10"]
```

### Held-out N=100 (planned only)

| Stratum | N_h | n_h | π_h | w_i |
|---|---:|---:|---:|---:|
| MQ/complete | 4 | 4 | 1.000000000000 | 1.000000000000 |
| MQ/partial | 44 | 36 | 0.818181818182 | 1.222222222222 |
| MQ/zero | 37 | 35 | 0.945945945946 | 1.057142857143 |
| SB/complete | 26 | 10 | 0.384615384615 | 2.600000000000 |
| SB/partial | 15 | 9 | 0.600000000000 | 1.666666666667 |
| SB/zero | 6 | 6 | 1.000000000000 | 1.000000000000 |

MQ/complete:
```json
["2hop__363216_787353", "3hop1__103254_214799_259594", "2hop__70338_36240", "2hop__488811_30113"]
```

MQ/partial:
```json
["4hop1__802394_153080_33897_81096", "3hop1__465684_160545_62931", "3hop1__106042_64399_59680", "2hop__525581_161450", "4hop1__47210_53706_795904_580996", "2hop__135822_46621", "2hop__677929_696450", "3hop1__147225_30587_83479", "4hop1__814349_624859_355213_203322", "3hop1__53690_161697_73916", "3hop2__72083_92991_76291", "2hop__119423_779396", "2hop__450600_158262", "2hop__640262_122868", "2hop__511454_120259", "4hop1__726675_508773_85832_745702", "3hop1__786067_228453_86925", "3hop2__304722_590317_63959", "2hop__415518_616002", "4hop3__152056_698586_91248_54362", "2hop__17192_77606", "3hop2__92991_28727_76291", "3hop1__64957_87694_64412", "3hop1__132795_40769_64047", "3hop1__791757_15840_36002", "2hop__203437_152093", "4hop1__72247_497223_15840_36014", "2hop__161273_92673", "3hop1__398232_326948_59893", "3hop2__222979_840908_40768", "4hop2__161602_474028_88460_20988", "2hop__495316_660579", "2hop__661847_288421", "3hop1__49236_89752_49923", "4hop3__519729_88460_30152_20999", "2hop__284613_87295"]
```

MQ/zero:
```json
["2hop__631139_75487", "3hop2__132957_433432_40768", "2hop__28287_89399", "2hop__846844_47134", "2hop__525242_52835", "2hop__486314_544665", "2hop__142621_225454", "2hop__458672_20057", "3hop1__640171_228453_86925", "3hop2__132957_51933_40768", "2hop__81659_52835", "3hop2__106842_30645_84681", "2hop__71755_463572", "2hop__284789_52835", "2hop__121386_37168", "2hop__31085_23241", "3hop1__133292_40769_64047", "2hop__433694_20273", "3hop1__389955_132457_47686", "3hop2__20335_8533_9331", "3hop1__389955_132457_51423", "2hop__280583_229757", "2hop__491195_265959", "2hop__307218_161450", "3hop1__41865_55331_34700", "2hop__6956_192417", "3hop1__131820_59747_48534", "2hop__60001_512508", "3hop2__84553_90098_10557", "2hop__496961_554601", "3hop1__83970_685536_47686", "3hop2__159979_30587_44003", "2hop__64175_90973", "2hop__67660_81007", "4hop1__88342_49853_128008_54974"]
```

SB/complete:
```json
["III-30_n10", "I-08_n5", "I-09_n10", "I-05_n5", "II-17_n10", "III-23_n5", "III-26_n5", "III-26_n10", "II-19_n5", "I-05_n10"]
```

SB/partial:
```json
["III-29_n5", "III-27_n5", "III-24_n5", "III-23_n10", "I-10_n10", "II-18_n10", "II-18_n5", "III-29_n10", "III-27_n10"]
```

SB/zero:
```json
["II-13_n10", "I-02_n5", "I-03_n5", "I-02_n10", "II-15_n5", "I-03_n10"]
```
## Interval-width planning and implementation

Simulate true κ in {0.70,0.75,0.80}, accuracy in {0.85,0.90}, instance ICC 0.25, 200 simulated panels per cell and 2,000 bootstrap draws per panel. Compare the old unstratified 60 and proposed stratified 60/80/100. Gold support units provide a conservative proxy for atomic-fact count; the lexical split determines simulated presence and trace-loss marginals, not human labels. Lexical labels cannot identify fidelity prevalence: conditional faithful proportions 0.85 and 0.95 are explicit sensitivity assumptions, with remaining mass 90% partial /10% distorted, no simulated uncertain labels. Do not assert that these are observed fidelity rates. Both primary statistics require approximately ±0.10 half-width, including fidelity; if no tested size meets that precision, recommend none rather than silently enlarging. Human labels are still needed to validate these planning assumptions.

Analysis: `src/audit/e1_weighted_analysis.py`, consuming explicitly human-adjudicated fact/carrier and trace records, rejects pilot-provisional data and out-of-design IDs. `scripts/simulate_e1_interval_width.py` is simulation only. Three model traces per instance, two annotation passes: MQ 7 minutes/trace, SB 20, plus 0.55 h/instance fact specification/adjudication; planned held-out totals 94.5/126/157.5 h for 60/80/100 (23.625/31.5/39.375 h per annotator). These replace only the held-out portion, not the separate dev/calibration budget.

## Matcher and technical pilot provenance

The current matcher remains dev-only `semantic-dev-v2`, Qwen `qwen/qwen3-235b-a22b-2507`, temperature 0, max output 4096, seed 42. Strict schema, at most two schema retries, every attempt logged; whitespace/one complete JSON fence only, no label repair. Failed eligible traces remain errors. Prompt+retry hash: `3d97341d410e0d2e93df919a28af59c7e2d389751ae43f6eb5258038f8ddc57c`; exact text is in E1-v2.md and the prompt snapshot. Lexical comparison thresholds remain {0,.1,.2,.3,.5}. Held-out prompts are not frozen. The reserved pilot still has 0/30 failed traces; those labels never enter this draw or human sheets.

Full initial call inventory remains 1,824 matcher calls (152×3 models×2 k×2 calls) +152 GPT prerequisites =1,976; maximum 5,624 attempts with two retries, not an execution authorisation.

Design manifest SHA-256: `9158f115be2e8b658cdb3f874ea173513b1953638dd9302aa8871b18119f0853`.
