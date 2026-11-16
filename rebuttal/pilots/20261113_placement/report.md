# Placement test v1 — labelling and pilot

Pre-registration `prereg/PLACEMENT-TEST-v1.md` (sha256 `2106171f034b`); action manifest `14c3dd5a056e`. Spend $0.121998.

Labels use the frozen **validated** labeller v2: `rebuttal/pilots/20261112_labeller/labeller_prompt_v2.json`, file sha256 `7f9e2816…8268c6`, system sha256 `585d0d45…b8e6e`. It was validated on 150 author-labelled traces (agreement 0.953, 95% CI 0.913-0.987; kappa 0.878, 0.760-0.965; `rebuttal/pilots/20261112_labeller_v2_full/full_report.md`). The labeller screens for evidence flow only; answer correctness below is the frozen exact rule.

**Labelled traces:** 78/78; DEFECT 65/78 (83.3%, 95% CI 73.2-90.8%), CORRECT 12, unparsed 1.

| model | n | DEFECT | CORRECT |
| --- | ---: | ---: | ---: |
| google | 26 | 19 | 7 |
| openai | 26 | 24 | 2 |
| qwen | 26 | 22 | 3 |

**Spot-check agreement:** 9/10 (90.0%, exact Clopper-Pearson 95% CI 55.5-99.7%). The hand labels were read by the worker (this assistant) from each rendered trace, without a model; selection was 4 CORRECT and 6 DEFECT-and-wrong traces, by `sha256("43|spot|" + trace_id)` within each stratum.

| trace | model | hand | labeller | agrees |
| --- | --- | --- | --- | --- |
| I-09_n10::seed43 | google | CORRECT | CORRECT | yes |
| I-04_n10::seed43 | openai | CORRECT | CORRECT | yes |
| I-04_n10::seed43 | google | CORRECT | CORRECT | yes |
| I-07_n10::seed43 | google | DEFECT | CORRECT | no |
| II-16_n10::seed43 | google | DEFECT | DEFECT | yes |
| I-05_n10::seed43 | google | DEFECT | DEFECT | yes |
| I-09_n10::seed43 | openai | DEFECT | DEFECT | yes |
| II-16_n10::seed43 | openai | DEFECT | DEFECT | yes |
| III-29_n10::seed43 | qwen | DEFECT | DEFECT | yes |
| III-30_n10::seed43 | qwen | DEFECT | DEFECT | yes |

## Placement pilot

| trace | model | base | target agent | hash agent | target | hash |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| III-28_n10::seed43 | google | no | 0 | 2 | no | no |
| III-27_n10::seed43 | google | no | 0 | 4 | no | no |
| II-13_n10::seed43 | openai | no | 0 | 5 | no | no |
| III-27_n10::seed43 | openai | no | 9 | 7 | no | no |
| II-17_n10::seed43 | qwen | no | 0 | 3 | no | no |
| III-28_n10::seed43 | qwen | no | 2 | 6 | no | no |

Target exact **0/6**, hash exact **0/6**; paired difference +0 at n=6 (**descriptive only**, no population claim). The six piloted traces are 4 unique instances: III-27 and III-28 each appear on two models. Many arms answered "Insufficient information", so one inserted line did not restore the evidence absent from the base trace.

- III-28_n10::seed43 / target: wrong — `Insufficient information.`
- III-28_n10::seed43 / hash: wrong — `Insufficient information.`
- III-27_n10::seed43 / target: wrong — `To find the top 3 user-item pairs, we first identify all available user vectors and item vectors from the provided evide`
- III-27_n10::seed43 / hash: wrong — `To find the top 3 user-item pairs, we first identify all available user vectors and item vectors from the provided evide`
- II-13_n10::seed43 / target: wrong — `Insufficient information.`
- II-13_n10::seed43 / hash: wrong — `Insufficient information.`
- III-27_n10::seed43 / target: wrong — `Insufficient information.`
- III-27_n10::seed43 / hash: wrong — `Insufficient information.`
- II-17_n10::seed43 / target: wrong — ``
- II-17_n10::seed43 / hash: wrong — `[23, -4, -31, 34, 42, -72, 35, -11, 68, -11, -18, -68, 15, 8, 74, 7, -83, 43, -5, -27, 26, 23, 37, -41, 1, 20, 10, -31, `
- III-28_n10::seed43 / target: wrong — `Insufficient information.`
- III-28_n10::seed43 / hash: wrong — `Insufficient information.`
