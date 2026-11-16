# Batch-1 pilot report — 2026-11-08

Technical snapshot; no full batch runs, commits, protected-plan or final-results edits. All five experiments have reserved-ID pilots; human validation and settings decisions still block freezing. D1=A, D11=A. No outcome is reported by failure group.

## External-method table (written before implementation)

| Method / source | Official assets, licence, pinned revision | Adaptation | Published-number sanity check | Extra effort | Risk |
|---|---|---|---|---:|---|
| W&W all-at-once; E2-C/A/B; [official repository](https://github.com/mingyin1/Agents_Failure_Attribution) | `Automated_FA/Lib/utils.py`; MIT; `b2bae5c5b06d681d04ea5e9b63b7a30525c04925` | Relay → numbered transcript; step → stage; Qwen/Gemini backbone swap; no type output | GPT-4o-mini appears in Figure 3 of arXiv:2505.00212v3; released all-at-once/data numerical sanity run below | 4 h | Medium: preserve official prompt and parsing; renderer changes observation granularity |
| W&W step-by-step; E2-A/B; same source | Same MIT code and pin | Sequential prefixes and stopping rule; same renderer/stage map and model swaps | Not established; do not claim reproduction | 6 h | High if replaced by repeated all-at-once; must preserve released control flow |
| W&W-Pro [R1] all-at-once; E2-C/A/B; [code](https://github.com/ag2ai/whowhen_pro), [paper](https://arxiv.org/html/2607.09996v2) | `whowhen_eval/prompts.py`; no code licence; `14369dcb079c7cdf86ed2924145d5a28ff5c73b2`; [taxonomy](https://huggingface.co/datasets/Leoxx/whowhen_pro/blob/0bd196c/taxonomy.yaml), CC-BY-4.0, `0bd196c` | Official prompt unchanged; relay RenderResult adapter; step → stage; frozen family/mode maps; Qwen/Gemini swap | Paper reports Gemma 4 but no 31B identifier found. Gemma variant could not be confirmed; structural check, not a numerical reproduction, completed below | 6 h | Medium/high: release has 17 modes vs paper 18; model ambiguity; no licence (D1=A). Keep unlicensed source outside release |
| MAST judge; E2-C/A/B; [official repository](https://github.com/multi-agent-systems-failure-taxonomy/MAST) | `taxonomy_definitions_examples/definitions.txt`, `llm_judge_pipeline.ipynb`; no licence; `a70542e541b2104ef8fcd785778179e173fb8d70` | Transcript renderer; mode → stage/type contingency only; reconcile notebook 3.2/3.3 with definitions; backbone swap | No like-for-like numerical reproduction established | 5 h | High if reduced to a new short prompt. Preserve released pipeline; no invented agent/step scores |
| Our E1 semantic audit; E2-A/B | Local `critical_fact_validation.py`, `alignment.py`; repository LICENSE; record file hashes (working tree is dirty) | Atomic/support-set carrier matcher; no external reimplementation | Existing lexical results are regression checks, not semantic ground truth | 10 h | Author labels required; ontology gaps count as errors |
| Our E6 proxy supports; E2-A/B | Own proposed method, local E6 card; not an external baseline | P-q/P-a; dev choice frozen before held-out; Qwen generator | No published number | 8 h | Batch-2 dependency; do not silently omit or substitute gold supports |
| E3 checkpoint ablation | **Only our own methods**; E3 card and local repair code | Remove checkpoints; identical action hashes required for reuse | Offline regression only | 4 h | No weak external reimplementation risk; route/target consistency risk |
| E6 Part A | **Only our own methods**; E6 card | Gold-free proxy generation and agreement evaluation | No published number | included above | Gold leakage and dev-selection risks |

Pins checked via GitHub API on 2026-11-08; API responses saved in `rebuttal/pilots/20261108_preflight/`. Effort estimates are engineering estimates, not elapsed time.

## Prices and corrected planning totals

OpenRouter route (`utility/apis/openrouter_api.py`), [provider pricing API](https://openrouter.ai/api/v1/models), saved 2026-11-08 in `20261108_preflight/pricing.json`. Input/output USD per million: Qwen-235B .14/.80; GPT-4o-mini .15/.60; Gemma-4-31B .20/.40; Gemini 3.6 Flash .75/3.75. Exact IDs remain in configs; no aliases substituted.

| Experiment | Initial calls | USD estimate | Annotation h |
|---|---|---|---|
| E1 | 1,976 | 1.27 | 112 |
| E4 | 7,668 | 4.39 | 8 |
| E4-P | 5,112 | 6.76 | 0 |
| E2-C | 72 | 0.14 | 0 |
| E2-A | 5,230 | 9.61 | 30 |
| **Batch 1 including E2-A** | **20,058** | **22.17** | **150 h; ≈9 days** |
| E2-B | 5,040 | 10.02 | 70 |
| E3 | 700 | 0.41 | 0 |
| E6-A | 1,700 | 1.15 | 5 |

E1 is now **1,976 initial calls**: 152 instances ×3 base models ×2 k ×2 matcher calls =1,824, plus152 GPT k=1 prerequisite aggregations. Dev/held-out validation overlaps this population. The obsolete approximate 3,700 matcher-call allowance is replaced by this explicit inventory; no additional matching pass is implemented. Three attempts maximum gives5,624 total attempts including prerequisites. E4 now includes four post-repair fidelity calls per case (1,704), correcting the old1,280 allowance.

Planning assumptions remain70/30 input/output,2k tokens per judge/baseline call, equal base-model shares, and repair weights300 MQ/63 SB5/63 SB10. These are initial-call estimates, not caps: source generation, calibration, retries, E2-A screening and E6 proxy costs are separate. E2-A200 candidate screening adds up to800 calls/≈$0.32. Measured released prompts are much longer than2k; use the operational estimates below before budgeting a full run. Calculator: `20261108_preflight/recompute_costs.py`.

## E4-P enlargement

| Option | Added N per type, projected from cache | Initial calls / USD | Annotation / days | Status |
|---|---|---|---|---|
| (a) SB seed43,26tasks×3models,k1,n10 | 78 traces: extraction≈16, selection≈40, aggregation≈12, strict distortion≈0–1 | 4,368 / $5.59 | 4 h (1/person);≈1 calendar day | Config switch OFF; one reserved item piloted separately |

Counts are projections, not observed new-seed groups. 40 pool +1 aggregation +2 matcher +12 placement +1 terminal =56 calls/trace before retries. Seed43 pilot outcomes are discarded; any approved full enlargement uses fresh calls and clusters by underlying task. **Option(b) dropped:** the paper has no second benchmark with established extraction and distortion groups.

## E1 dev repair and sample feasibility

Old PID 77158 finished before v2 started; its ledger remains unchanged. `semantic-dev-v2` fixes required fields, ID enums and joint-carrier cardinality with JSON-schema output. At most2 retries per logical call, every attempt logged. Parser leniency is only whitespace and one complete JSON fence; duplicate keys, trailing braces, missing fields and invalid roles fail. No labels are repaired. Exhausted traces remain `failed`, counted as errors in eligible matcher-accuracy denominators; human κ is independent of matcher success. No held-out prompt is frozen.

Prompt+retry SHA-256: `3d97341d410e0d2e93df919a28af59c7e2d389751ae43f6eb5258038f8ddc57c`. Same five reserved IDs,30 cached source traces, Qwen judge throughout.

| Base model / k | Failed traces | Retried logical calls |
|---|---|---|
| google/gemma-4-31b-it/k1 | 0/5 | 0/10 |
| google/gemma-4-31b-it/k3 | 0/5 | 0/10 |
| openai/gpt-4o-mini/k1 | 0/5 | 0/10 |
| openai/gpt-4o-mini/k3 | 0/5 | 0/10 |
| qwen/qwen3-235b-a22b-2507/k1 | 0/5 | 0/10 |
| qwen/qwen3-235b-a22b-2507/k3 | 0/5 | 0/10 |

Final failure rate **0/30=0%**, below5%; retry rate **0/60=0%**. This small dev sample does not establish a population failure rate. Measured matcher:60 calls,$0.018822,263.5 summed API seconds;2 calls/$0.000627/8.78s per trace. Applied to912 full traces:1,824 calls/$0.57/2.22 serial API hours, plus152 prerequisites. Planning comparator:1,824 matcher calls/$1.23 under2k tokens. MuSiQue-only throughput is not a Silo-Bench guarantee.

| Cached held-out proxy | Instances | Wrong traces | Known partial proxy excluded | Binary eligible | Lost / unused |
|---|---|---|---|---|---|
| MQ | 45 | 75 | 0 | 75 | 0 / 75 |
| SB | 15 | 25 | 5 | 20 | 10 / 10 |
| pooled | 60 | 100 | 5 | 95 | 10 / 85 |

Cached k=3 lexical labels estimate prevalence, not human labels. Only cached Qwen SB partial flags are available (any partial conservatively excluded); other partial/uncertain labels are unknown, so95 is provisional. Simulation:300 replicates/cell,2,000 instance-cluster bootstrap draws, seed42, ICC.25 (0/.5 sensitivity in JSON). Cells below give probability that the relevant lower95% bound clears. κ probabilities vary slightly across paired accuracy simulations due to Monte Carlo error (up to≈3 percentage points SE).

| Benchmark | True κ | κ bound≥.60 (acc .85/.90) | Accuracy bound≥.80 (.85/.90) | Both (.85/.90) |
|---|---|---|---|---|
| MQ | 0.7 | 0.0% / 0.0% | 23.7% / 67.7% | 0.0% / 0.0% |
| MQ | 0.75 | 0.0% / 0.0% | 28.0% / 61.0% | 0.0% / 0.0% |
| MQ | 0.8 | 0.0% / 0.0% | 28.0% / 67.3% | 0.0% / 0.0% |
| SB | 0.7 | 18.3% / 17.7% | 21.7% / 41.0% | 4.3% / 7.3% |
| SB | 0.75 | 25.7% / 23.0% | 20.7% / 45.0% | 4.7% / 10.7% |
| SB | 0.8 | 36.3% / 38.3% | 22.0% / 42.7% | 4.7% / 16.3% |
| pooled | 0.7 | 10.3% / 9.7% | 29.3% / 68.3% | 2.3% / 6.3% |
| pooled | 0.75 | 21.0% / 18.7% | 26.0% / 70.7% | 5.3% / 13.3% |
| pooled | 0.8 | 32.7% / 32.3% | 27.7% / 72.7% | 9.0% / 25.3% |

At MQ lost prevalence0, κ is undefined; increasing N alone cannot fix it. Under pooled prevalence10.5%, the coarse grid needs720 instances at κ=.75/accuracy=.85 (joint power90.7%; +660 instances,≈1,039.5 extra annotation h) or480 at accuracy=.90 (82%; +420,≈661.5 h). These exceed the existing population. MQ sensitivity at10% lost needs720/480 instances (+843.75/+543.75 h); at5% lost even720 does not reach80%. SB needs480/180 (+1,185.75/+420.75 h). Hours include two passes over3 model traces, fact specification and adjudication; grid estimates are scenario-dependent, not precise power guarantees. **No enlargement made.** Full scenarios: `20261108_preflight/e1_power.json`.

## Pilot decisions and operational measurements

Every downstream item is `pilot_provisional`, disjoint from final/calibration IDs; labels never enter annotation sheets or final evaluation. Technical E2-A deliberately exercises baselines on unkept/ineligible items; those are not causal-validation examples. Full-run decisions remain separate from technical readiness.

| Experiment | Decision | Reason |
|---|---|---|
| E1 | GO technical / FIX freeze | Schema target met; pending human calibration, thresholds and sample feasibility. |
| E4 | FIX | All 10 arms ran; exact base tokenizers find only 6/15 volume-matched pairs. Unmatched controls cannot enter matched primary analysis; donor/control selection needs work. |
| E4-P | GO technical | Three placements ran, terminal outcomes reused with identical prompt/model/seed hashes; no duplicate comparator calls. Full run awaits validated targets. |
| E2-C | FIX | All 3 official methods×2 backbones ran; attribution output omissions remain; casebook labels provisional. |
| E2-A | FIX | Injection/rerun/baseline path exercised; human single-defect checks absent. Provisional keep is not card-qualified keep; Both E6 proxy variants also piloted. Post-pilot keep-gate review tightened the single-defect check; human confirmation remains required. |

| Pilot | Items done | Measured calls / USD / API seconds | Per completed item | Full-cohort mechanical projection calls/USD/API h |
|---|---|---|---|---|
| E1 | 30/30 | 60 / $0.018822 / 263.5s | 2.0 / $0.00063 / 8.8s | 1,824 / $0.57 / 2.22h |
| E4 | 5/5 | 91 / $0.024564 / 263.3s | 18.2 / $0.00491 / 52.7s | 7,753 / $2.09 / 6.23h |
| E4-P | 5/5 | 54 / $0.034652 / 107.0s | 10.8 / $0.00693 / 21.4s | 4,601 / $2.95 / 2.53h |
| E2-C | 5/5 | 30 / $0.217669 / 316.2s | 6.0 / $0.04353 / 63.2s | 72 / $0.52 / 0.21h |
| E2-A | 5/5 | 155 / $0.567509 / 900.1s | 31.0 / $0.11350 / 180.0s | 6,200 / $22.70 / 10.00h |

API seconds sum individual latency, not wall time. E2-A200-case projection is a candidate workload estimate, not200 human-qualified injections, and excludes proxy supplement. E4/P estimates include observed retries/unit counts, not worst-case caps. Tiny MQ pilots do not justify SB throughput.

| Separately costed job | Calls | USD | API seconds |
|---|---|---|---|
| e2_a_proxy | 35 | $0.011430 | 156.9 |
| e4_p_seed43 | 56 | $0.030872 | 191.6 |
| r1_structural | 5 | $0.002672 | 16.8 |
| ww_sanity | 315 | $0.301724 | 1066.9 |
| e1 | 206 | $0.022344 | 523.2 |
| e1_calibration | 171 | $0.013231 | 425.6 |

E4-P extra seed completed 1 reserved item:56 calls,≈$0.03087,191.6s including source generation. The full switch remains off. E4 post-fidelity had 1 retried logical call and 0 exhausted calls. Exact tokenizers: Qwen HF revision `ac9c66cc9b46af7306746a9250f23d47083d689e`, Gemma HF revision `842da3794eaa0b77d5f08bae87a17459d91ff475`, and GPT-4o-mini tiktoken model mapping. Counts apply only to added/replacement unit text with the base tokenizer; no Gemini tokenizer is needed. No API errors/timeouts were logged in these snapshots. No provider safety-refusal finish reason was recorded; raw content is retained, and “Insufficient information” is not counted as a safety refusal.

| Technical output validation | Failures / outputs |
|---|---|
| e2_c_technical ww_all | 1/10 |
| e2_c_technical r1 | 5/10 |
| e2_c_technical mast | 0/10 |
| e2_a_technical ww_all | 1/20 |
| e2_a_technical r1 | 11/20 |
| e2_a_technical mast | 0/20 |
| e2_a_technical ww_step | 7/20 |

Validation uses current layout parser on immutable raw text: optional “Step ” prefix is stripped, with no changed coordinate or label. W&W step-by-step uses released stdout attribution/stopping, not a requirement that each yes/no response contain an agent. Missing R1 taxonomy names remain invalid. No published prompt is altered to improve output compliance.

## External sanity checks

**[R1]: structural check, not a numerical reproduction.** The Gemma variant could not be confirmed as Gemma-4-31B. Released prompt and17-mode taxonomy unchanged, Qwen-235B on five own ALFWorld example traces.

| Check | Result |
|---|---|
| Agent/step/mode parse | 5/5; parse-failure rate0% |
| Valid code+name pair | 4/5; one code-only R.4, not repaired |
| Mode code valid | 5/5 |
| Step in trace | 5/5 after documented layout normalisation |

**Who&When:** [paper](https://arxiv.org/abs/2505.00212), Figure3 in v3, explicitly reports GPT-4o-mini. Released all-at-once code/data at the pinned commit are running on184 native traces, with and without ground truth (368 conditions), using only GPT-4o-mini. Completed **315/368**. Current pooled native released-evaluator agent/step accuracy: **51.43%/8.25%**; strict equality sensitivity **51.43%/6.98%**. Parse success100.0%. These are partial results, not a completed numerical reproduction; proximity cannot be concluded yet. The radar chart provides no exact text labels; visual readings≈55%/≈4% have roughly±2-point uncertainty. OpenRouter versus historical Azure deployment, unknown historic model snapshot, and averaging across gold conditions/system types limit exact reproduction. The released evaluator uses substring matching; strict equality is reported separately rather than silently changing the metric. No other paper model is substituted.

## Raw examples

First three immutable filenames per experiment, chosen without labels or outcomes; excerpts truncated only for report length. Full raw files remain linked by path.

### e1_v2

| Raw file | Unedited excerpt |
|---|---|
| rebuttal/pilots/20261108_e1_v2/matcher/095ad327fe4333ff0bae9bdc088b03c9c75680935166c13eb5a259f35e806c6e.json | {"facts": [{"board": [{"fidelity": "faithful", "role": "sole", "unit_ids": ["pool:a1:u0"]}], "extraction": [{"fidelity": "faithful", "role": "sole", "unit_ids": ["pool:a1:u0"]}], "fact_id": "f1"}, {"board": [{"fidelity": "faithful", "role": "sole", "unit_ids": ["pool:a1:u1"]}], "extraction": [{"fidelity": "faithful", " |
| rebuttal/pilots/20261108_e1_v2/matcher/097b81ab935df9d4a061838e851f65c92124027bc1f8cb93c9c27f69ff1f7b43.json | {"facts": [{"board": [{"fidelity": "distorted", "role": "sole", "unit_ids": ["pool:a0:u1"]}], "extraction": [{"fidelity": "faithful", "role": "sole", "unit_ids": ["pool:a0:u0"]}], "fact_id": "f1"}, {"board": [], "extraction": [{"fidelity": "faithful", "role": "sole", "unit_ids": ["pool:a1:u0"]}], "fact_id": "f2"}, {"bo |
| rebuttal/pilots/20261108_e1_v2/matcher/0ea027562b11a94946121da6fc7e79d4c59e751040dd9deb4d5d17763289af9c.json | {"facts": [{"board": [{"fidelity": "faithful", "role": "sole", "unit_ids": ["pool:a0:u0"]}], "extraction": [{"fidelity": "faithful", "role": "sole", "unit_ids": ["pool:a0:u0"]}], "fact_id": "f1"}, {"board": [{"fidelity": "faithful", "role": "sole", "unit_ids": ["pool:a1:u0"]}], "extraction": [{"fidelity": "faithful", " |

### e4_technical

| Raw file | Unedited excerpt |
|---|---|
| rebuttal/pilots/20261108_e4_technical/raw/26e9a63ebc1d0b7e498d19fc3d7e2f4e853c19b5c62335d2dd608c7c47680232.json | ANSWER: Ahinoam   USED_EVIDENCE: 1, 1   RATIONALE: The evidence states that Ahinoam is the wife of Saul, who is identified as the first king of Israel. |
| rebuttal/pilots/20261108_e4_technical/raw/3df6a80e61502fd184f78f0d76599a73a32c4a8782534ac196d7f1a35ffd7c1c.json | ANSWER: Insufficient information.   USED_EVIDENCE:   RATIONALE: The provided evidence units confirm that the Carolina Hurricanes are part of the NHL, but neither unit specifies when the NHL regular season begins. |
| rebuttal/pilots/20261108_e4_technical/raw/3f73251b0c0a5a9555b300a088e9a19ab95fe99f1b9ec2edfca0181b08b097db.json | ANSWER: Insufficient information. USED_EVIDENCE:  RATIONALE: The provided evidence does not specify any treaty related to the Minikahda Club or its geographical context. |

### e4_p_technical

| Raw file | Unedited excerpt |
|---|---|
| rebuttal/pilots/20261108_e4_p_technical/raw/26e9a63ebc1d0b7e498d19fc3d7e2f4e853c19b5c62335d2dd608c7c47680232.json | ANSWER: Ahinoam   USED_EVIDENCE: 1, 1   RATIONALE: The evidence states that Ahinoam is the wife of Saul, who is identified as the first king of Israel. |
| rebuttal/pilots/20261108_e4_p_technical/raw/3df6a80e61502fd184f78f0d76599a73a32c4a8782534ac196d7f1a35ffd7c1c.json | ANSWER: October 4, 2017   USED_EVIDENCE: 1, 1   RATIONALE: The Carolina Hurricanes belong to the NHL, and the 2017–18 NHL regular season began on October 4, 2017, as stated in the evidence. |
| rebuttal/pilots/20261108_e4_p_technical/raw/3f73251b0c0a5a9555b300a088e9a19ab95fe99f1b9ec2edfca0181b08b097db.json | ANSWER: Insufficient information. USED_EVIDENCE:  RATIONALE: The provided evidence does not specify any treaty related to the Minikahda Club or its geographical context. |

### e2_c_technical

| Raw file | Unedited excerpt |
|---|---|
| rebuttal/pilots/20261108_e2_c_technical/raw/097b81ab935df9d4a061838e851f65c92124027bc1f8cb93c9c27f69ff1f7b43.json | Agent Name: agent-1   Step Number: 1   Reason for Mistake: The Minikahda Club is located in Minneapolis, Minnesota, which lies near **Lake Calhoun** (now officially Bde Maka Ska), a freshwater lake that is part of the Mississippi River watershed—not connected to any western body of water ceded by treaty such as the Pac |
| rebuttal/pilots/20261108_e2_c_technical/raw/11a96876848b74164948781df432837322bd4c2b0924a074134eb7511b6bac21.json | Agent Name: agent-1   Step Number: 1   Reason for Mistake: The error lies in agent-1's claim that "The song 'Good Little Girls' was written by Troy Seals and Brett Jones." This statement is factually incorrect and introduces misleading information. "Good Little Girls" was actually written by Aaron Benward, Scott Reeves |
| rebuttal/pilots/20261108_e2_c_technical/raw/2ac76b59d8e27c979a2014599679cd7ceaa4bcbe6daaee4f28b70b98717db514.json | Agent Name: agent-0   Step Number: 0   Reason for Mistake: The agent incorrectly identifies Ahinoam as the wife of Saul, the first king of Israel. According to the Hebrew Bible (1 Samuel 14:50), Saul’s wife was Ahinoam, so this statement is actually correct. However, the error lies in the fact that the Bible does not c |

### e2_a_technical

| Raw file | Unedited excerpt |
|---|---|
| rebuttal/pilots/20261108_e2_a_technical/raw/097b81ab935df9d4a061838e851f65c92124027bc1f8cb93c9c27f69ff1f7b43.json | ANSWER: Insufficient information. USED_EVIDENCE:  RATIONALE: The evidence provided does not specify the location of the Minikahda Club or the relevant treaty that ceded territory extending west to a body of water near it.  /  ANSWER: Insufficient information. USED_EVIDENCE:  RATIONALE: The provided evidence does not spec |
| rebuttal/pilots/20261108_e2_a_technical/raw/11a96876848b74164948781df432837322bd4c2b0924a074134eb7511b6bac21.json | ANSWER: Insufficient information.   USED_EVIDENCE: 1, 1   RATIONALE: The evidence units provide information about the song "Good Little Girls" and its chart performance, as well as identifying Blue County as the duo that recorded it, but they do not list any individual members of the duo.  /  ANSWER: Insufficient informa |
| rebuttal/pilots/20261108_e2_a_technical/raw/2ac76b59d8e27c979a2014599679cd7ceaa4bcbe6daaee4f28b70b98717db514.json | ANSWER: Ahinoam   USED_EVIDENCE: 1   RATIONALE: The evidence states that Ahinoam is referenced as the wife of Saul, who is identified as the first king of Israel.  /  ANSWER: Ahinoam   USED_EVIDENCE: 1   RATIONALE: The evidence states that Ahinoam is referenced as the wife of Saul, who is identified as the first king of  |

### r1_structural

| Raw file | Unedited excerpt |
|---|---|
| rebuttal/pilots/20261108_r1_structural/alfworld_alfagent_0001.json | Agent Name: agent   Step Number: Step 4   Error Mode: R.2: Reasoning Error   Reason: At Step 4, the agent incorrectly believes it has already picked up both pencils, but it has only taken pencil 1 and has not yet taken pencil 2. This is a grounded misapplication of its observation history — it saw pencil 2 still on the |
| rebuttal/pilots/20261108_r1_structural/alfworld_alfagent_0002.json | Agent Name: agent   Step Number: Step 14   Error Mode: R.2: Reasoning Error   Reason: The agent correctly identifies soapbottle 1 on countertop 2, but fails to recognize that it needs to find a second soapbottle to complete the task. Instead of searching for another soapbottle, it proceeds to move the same soapbottle r |
| rebuttal/pilots/20261108_r1_structural/alfworld_alfagent_0003.json | Agent Name: agent   Step Number: 2   Error Mode: R.2: Reasoning Error   Reason: The agent incorrectly assumes that the fridge is the appropriate place to clean a spatula, which is a grounded misapplication of knowledge—cleaning typically occurs in a sink with water and soap, not in a fridge. This wrong reasoning derail |

## Annotation and verification

Packages remain under `rebuttal/annotation/`: E1 reach/fidelity; nonblind E2-A base screening and postchecks; E4 matcher40 spot checks and source swaps; blind E2-B guidelines for batch2. Each has schema,5 synthetic worked examples and sheets. Five separate calibration sources exist; **human calibration has not happened**, so no human agreement is claimed. Pilot-provisional matcher/baseline outputs are never exported to these sheets.

Four-annotator rotation: E1 A+B with C+D on alternate instances; Part B uses the complementary pair, retaining assignments across models. Recursive allowlist export hides all audit verdicts, matcher/lexical scores and baseline outputs (tested). Main-study hours/person: E1 28, E2-A 7.5, E4 2 =37.5; Part B later 17.5; calibration reserve2.1 extra. Calibration statistics: E1 binary κ; E2-A eligibility/keep κ; E4 fidelity/swap validity κ; E2-B class and reference κ separately. Actual post-injection and repair verification remains author work, not simulated annotation.

Full `.conda-env/bin/python -m pytest -q`: **274 passed** (`20261108_preflight/pytest_v2.log`). Tests include scoring, deterministic manifests/disjoint IDs, instance bootstrap/κ, renderer/blind export, taxonomy mapping, strict parser/two-retry exhaustion, exact tokenizers, official sequential control flow, and terminal-comparator reuse guards. No full experiment was launched.

## Preregistration hashes

Design files and technical supplements are distinct. Pilot ledger `run_identity.json` binds the exact prereg/config at dispatch; archived E1-v1 preserves old design. E2-A-technical contains an earlier base-config hash plus the injection schedule addendum fixed before calls; the authoritative dispatched config hash is its run_identity, not that earlier base hash. No live prereg was edited after dispatch. E2-A keep-gate code was tightened after the pilot; `keep_gate_review.json` records conservative re-evaluation without changing raw labels or outcomes.

| File under prereg/ | SHA-256 |
|---|---|
| E1-v1.md | `90e7f359b846a1fb64bd1df8df3caf0bbd959732a78bd165efb027867138896e` |
| E1-v2.md | `f75782e3090726b0b2b7ad620bfee2ac1394903e61712449a89690d7c0c811d9` |
| E1.md | `e13f169dac6c252a2b9a5fcff7227139a552fc7fb252d3e55d4c7abe17c0bb07` |
| E2-A-proxy.md | `08a21f2f11e95b9f6eaaf2a7429252f38b73a8d5d03361b6df054095a248f4f1` |
| E2-A-technical.md | `490e7864b109999de5c4e49aec2987115cf9695d3fc1324b135f6aa98dbb8b81` |
| E2-A.md | `2cc504c972955193cf107b33c192ad6352e8860424ba0b892d5d8880e48adcc7` |
| E2-C-technical.md | `131904da4856fe6295243cac824c7624a57c9aa98f06c17d5abc7cb0168ad241` |
| E2-C.md | `e8ef11d946ffd1b2c7f0d17c20b5bd5a101ba28310a4cc7d10b67d8fc45db8bc` |
| E4-P-seed43.md | `01d93bc6c4432e3afb2f40ad42d55e3573dd32c704ff8892d27d87b5b4f03ba6` |
| E4-P-technical.md | `bf2b19cd257fba8d86d0dcbd836c1641c1e2837f1e1ed64323273f85af5828e3` |
| E4-P.md | `49f3a0369da22b8024dcae84a4e3ce181ca8e0db2bd8c2fa23fb2ab40cea9a66` |
| E4-technical.md | `33c38be896c7ed91f841e913501b44f5aae1316c354cb7b2f207a625b8cd5985` |
| E4.md | `dccedd654200945699912ed7a7e0fa9166742e47641cf6cbc3e90f3cac2189e4` |
| R1-structural.md | `547c570dacc847a1cb0dcf4b23bb4e01bdc8bf1b55add90f5c610bcec77bf08a` |
| WW-sanity.md | `b9c1edbc53af64fe1243c4962c982eecf41d90c1236986ea1afeb2817832778e` |

## Jobs and logs

Detached subprocesses use append-only call ledgers, exclusive worker locks, cumulative caps, pre-dispatch fsync, prompt/config/prereg hashes, model/seed/tokens/cost/latency. No automatic transport retries or uncertain-dispatch retries. Never start a second worker on an existing ledger. Status is determined from outputs below; completed PIDs are historical.

| Job | PID | Command | Log |
|---|---|---|---|
| e1_v2 | 26964 | `.conda-env/bin/python -u -m scripts.pilot_e1_v2 --execute --max-calls 180` | rebuttal/pilots/20261108_e1_v2/run.log |
| e4_technical | 68168 | `.conda-env/bin/python -u -m scripts.pilot_e4 --config rebuttal/pilots/configs/E4-technical.json --execute --max-calls 130` | rebuttal/pilots/20261108_e4_technical/run.log |
| e4_p_technical | 12375 | `.conda-env/bin/python -u -m scripts.pilot_e4p --config rebuttal/pilots/configs/E4-P-technical.json --execute --max-calls 60` | rebuttal/pilots/20261108_e4_p_technical/run.log |
| e2_c_technical | 68169 | `.conda-env/bin/python -u -m scripts.pilot_e2c --config rebuttal/pilots/configs/E2-C-technical.json --execute --max-calls 30` | rebuttal/pilots/20261108_e2_c_technical/run.log |
| e2_a_technical | 68170 | `.conda-env/bin/python -u -m scripts.pilot_e2a --config rebuttal/pilots/configs/E2-A-technical.json --execute --max-calls 260` | rebuttal/pilots/20261108_e2_a_technical/run.log |
| e2_a_proxy | 36019 | `.conda-env/bin/python -u -m scripts.pilot_e2a_proxy --execute --max-calls 75` | rebuttal/pilots/20261108_e2_a_proxy/run.log |
| e4_p_seed43 | 82660 | `.conda-env/bin/python -u -m scripts.pilot_e4p_extra_seed --execute --max-calls 60` | rebuttal/pilots/20261108_e4_p_seed43/run.log |
| r1_structural | 39350 | `.conda-env/bin/python -u -m scripts.check_r1_structure --execute --max-calls 5` | rebuttal/pilots/20261108_r1_structural/run.log |
| ww_sanity | 73598 | `.conda-env/bin/python -u -m scripts.reproduce_whowhen --execute --max-calls 368` | rebuttal/pilots/20261108_ww_sanity/run.log |

Refresh operational snapshot with `.conda-env/bin/python -m scripts.write_batch1_report` (read-only ledgers; report update only). Full raw responses and append-only call attempts are beside each log. Proxy PID 18254 stopped after four available injections; PID 36019 resumed its existing ledger once the fifth injection existed, reusing all prior calls.

## Settings changes for approval

1. **Internal CI criteria:** lower95% human κ≥.60 and matcher accuracy≥.80 were new criteria, not in the approved card. Kept pending lead approval in E1 prereg; rebuttal reports estimates/CIs, not pass/fail. No dependent freeze.
2. **Partial exclusion:** binary primary excludes partial (and uncertain) traces; partial exclusion was inferred from D6=C, which only explicitly keeps partial separate descriptively. Confirm the binary exclusion before freezing.
3. **Held-out sample:** simulations do not support the planned sample at the middle assumptions. Pooled proposals require480–720 instances,≈661.5–1,039.5 extra annotation h, with new data beyond the current population. Do not enlarge until approved; MuSiQue all-unused prevalence cannot yield κ at any N.
4. **E4-P extra seed(a):** implemented, switch off. One reserved technical item is authorised and completed; full enlargement remains subject to author confirmation.

Exact tokenizers are implementation of the approved card, **not a hold**. R1 structural check is already authorised and completed, **not a hold**. Option(b) is dropped, **not a hold**.

## Author decisions and recommended defaults

Keep D1=A, D11=A; no full runs. Review the E1 thresholds, partial exclusion and sample feasibility together before freezing. Keep E4 unmatched controls out of matched analyses while correcting donor selection; do not relax±10%. Complete human calibration/screening/single-defect checks. Retain both E6 proxy variants as dev-only until the card’s dev choice is made. Finish the running Who&When sanity job and refresh this report; do not duplicate it. These technical pilots do not overturn the reviewer’s overall FAIL or certify scientific readiness.
