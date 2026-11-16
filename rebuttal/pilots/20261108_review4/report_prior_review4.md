# Batch-1 pilot report — review 3, 2026-11-08

All five reserved-ID technical pilots completed; overall review verdict remains **FAIL**. No full batch runs, commits or protected-file edits. Human validation and proposed settings remain unfrozen.

| Experiment | Decision | What blocks it |
|---|---|---|
| E1 | GO schema pilot; FIX design freeze | Plan A and stratified draw pending; no tested size reaches ±0.10 fidelity κ precision under planning assumptions; human labels absent. |
| E4 | FIX | Donor re-pilot improves 6/15 → 7/15 matched controls; selection clarification pending and most cases have only one eligible donor. |
| E4-P | GO technical | Seed 43 approved and enabled for the full-run config; final targets still depend on human validation. |
| E2-C | FIX | Strict R1 invalidity 5/10 (missing mode names); casebook references remain provisional. |
| E2-A | FIX | Strict R1 invalidity 11/20; W&W step abstains 7/20; no human-qualified kept injections. |

## E1: interval-width design, not acceptance thresholds

The κ/accuracy acceptance thresholds are removed. The rebuttal reports estimates and 95% CIs only. `prereg/E1.md` now fully specifies proposed fact-level presence/fidelity primaries, trace-level binary secondaries, lexical sampling, inclusion probabilities, weights and fixed IDs for 60, 80 and 100 held-out instances. These are **planned, pending author confirmation**; no sample enlargement or matcher freeze has occurred.

| Lexical τ = 0.5 stratum | Frame N | Draw 60 | Draw 80 | Draw 100 |
|---|---|---|---|---|
| MQ/complete | 4 | 4 | 4 | 4 |
| MQ/partial | 44 | 21 | 28 | 36 |
| MQ/zero | 37 | 20 | 28 | 35 |
| SB/complete | 26 | 5 | 7 | 10 |
| SB/partial | 15 | 5 | 7 | 9 |
| SB/zero | 6 | 5 | 6 | 6 |

The frame excludes 20 fixed dev instances, leaving 85 MuSiQue and 47 Silo-Bench instances. Strata use only cached Qwen k = 3 lexical coverage: zero, incomplete, complete. Neither correctness nor matcher output selects IDs. Within strata, fixed SHA ordering uses `["E1-lexical-v3", 42, stratum, instance_id]`. Inclusion probability is **πₕ = nₕ/Nₕ**, weight **wᵢ = Nₕ/nₕ**; all model/fact rows inherit the instance weight. The full ID lists and exact weights are in the prereg and `20261108_review3/e1_stratified_design.json`.

The analysis script `src/audit/e1_weighted_analysis.py` reports weighted human κ and matcher accuracy for fact presence and fidelity, separately; 2,000 bootstrap draws resample whole instances within lexical strata. Board is the primary checkpoint; extraction is separate. Failed machine labels remain errors. Trace binary primary excludes partial/uncertain with counts; sensitivity counts partial as lost, still excludes uncertain. **Human labels do not exist yet, so whether these analyses change conclusions is not known.** Both will be reported.

Named outputs **`MQ_candidate_aggregation_failure_rate_human`** and **`SB_candidate_aggregation_failure_rate_human`** directly address the 68% headline. Denominator: all traces, including correct answers; numerator: wrong traces with a human-validated faithfully complete support set on the board. Pooled and per-model estimates include the 20 dev instances as human-labelled certainty units; validation statistics exclude them. The script refuses a full-frame rate without those dev labels. It also reports an unresolved-case upper sensitivity; no model-derived label substitutes for a human reference.

### Expected 95% CI half-widths

Each cell is κ / accuracy half-width. Central setting: true κ = 0.75, accuracy = 0.85; brackets give the range over κ = 0.70–0.80 and accuracy = 0.85–0.90. Instance ICC = 0.25; 200 simulated panels per cell, each with 2,000 bootstrap draws. Lexical τ = 0.5 provides the presence/trace split. Gold support-unit count is a conservative proxy for atomic-fact count.

| Held-out draw | Fact presence | Fact fidelity: 85% faithful | Fact fidelity: 95% faithful | Trace binary |
|---|---|---|---|---|
| original60 | 0.097 / 0.050 [0.088–0.114 / 0.042–0.053] | 0.163 / 0.078 [0.134–0.169 / 0.051–0.078] | 0.240 / 0.073 [0.214–0.263 / 0.054–0.077] | 0.319 / 0.088 [0.276–0.322 / 0.072–0.091] |
| 60 | 0.106 / 0.054 [0.090–0.112 / 0.043–0.058] | 0.148 / 0.089 [0.130–0.168 / 0.060–0.089] | 0.235 / 0.072 [0.208–0.263 / 0.061–0.085] | 0.166 / 0.073 [0.144–0.189 / 0.060–0.076] |
| 80 | 0.088 / 0.054 [0.077–0.105 / 0.038–0.054] | 0.142 / 0.075 [0.123–0.163 / 0.050–0.075] | 0.209 / 0.075 [0.178–0.245 / 0.057–0.077] | 0.149 / 0.066 [0.125–0.163 / 0.052–0.066] |
| 100 | 0.083 / 0.044 [0.070–0.087 / 0.036–0.047] | 0.134 / 0.070 [0.119–0.148 / 0.051–0.070] | 0.195 / 0.065 [0.170–0.201 / 0.050–0.069] | 0.134 / 0.057 [0.117–0.151 / 0.047–0.058] |

Lexical coverage **cannot identify fidelity prevalence**. The 85%/95% faithful splits are sensitivity assumptions, with remaining mass 90% partial and 10% distorted; they are not observed labels. Joint carrier groups are collapsed to one fidelity call per atomic fact using the prereg rule. The simulation models one fact per gold support unit, three model traces, no uncertain exclusions and no finite-population correction; more exclusions or different atomic granularity change precision. `e1_interval_width.json` contains all scenarios and undefined-κ frequencies. The old 10/85 split came from the historical low-threshold labels; it is not reused for the new τ = 0.5 draw.

| Held-out N | Held-out annotation h | Per annotator h | Extra vs 60 | Total E1 h including unchanged dev budget |
|---|---|---|---|---|
| 60 | 94.5 | 23.62 | 0.0 | 112.0 |
| 80 | 126.0 | 31.50 | 31.5 | 143.5 |
| 100 | 157.5 | 39.38 | 63.0 | 175.0 |

Hours assume two passes over three model traces (7 minutes each on MQ, 20 on SB), plus 0.55 h per instance for fact specification/adjudication. Calibration remains separate. **Recommendation: none of 60/80/100 meets ±0.10 on both primary statistics once fidelity κ is included.** Presence alone is near the target at 80; at 100 fidelity κ still has central half-width 0.134–0.195. Keep 60 as the unexpanded planning budget while authors confirm Plan A and review the fidelity prevalence/granularity assumptions; do not describe 100 as adequately precise. No larger population was invented or sampled.

### E1 technical matcher result retained

`semantic-dev-v2` remains unfrozen: strict schema; at most two retries per logical call; every attempt logged; only whitespace/one complete JSON fence tolerated, never repaired labels. Same five reserved IDs and 30 traces: **0/30 failed, 0/60 logical calls retried**. Each base-model × k cell is 0/5 failed (Qwen-235B, GPT-4o-mini, Gemma-4-31B; k = 1 and 3), Qwen judge throughout. Prompt+retry hash: `3d97341d410e0d2e93df919a28af59c7e2d389751ae43f6eb5258038f8ddc57c`. Full initial inventory remains **1,976 calls**: 1,824 matcher + 152 GPT prerequisites. Measured 60 matcher calls cost $0.018822 and 263.5 API seconds; projected matcher-only cost $0.57 / 2.22 serial API hours, versus $1.23 at the 2k-token planning assumption.

## Baseline validity and strict/code-only scoring

`prereg/Baseline-scoring-v3.md` fixes strict primary (invalid = wrong, retained denominator) and code-only sensitivity, planned pending confirmation for final evaluation. Current pilot rescoring is retrospective diagnostics. Released prompts and taxonomy are unchanged. The sensitivity accepts a valid mode code without its name only when agent and step are valid; it never changes a code or fills a label. W&W step-by-step uses its actual released stopping rule and native zero-based coordinate.

| Experiment | Benchmark | Method | Backbone | Strict invalid | Code-only invalid | Cause |
|---|---|---|---|---|---|---|
| E2-A | MuSiQue | mast | gemini-3.6-flash | 0/10 (0%) | not applicable | none |
| E2-C | MuSiQue | mast | gemini-3.6-flash | 0/5 (0%) | not applicable | none |
| E2-A | MuSiQue | mast | qwen3-235b-a22b-2507 | 0/10 (0%) | not applicable | none |
| E2-C | MuSiQue | mast | qwen3-235b-a22b-2507 | 0/5 (0%) | not applicable | none |
| E2-A | MuSiQue | r1 | gemini-3.6-flash | 8/10 (80%) | 0/10 | missing mode name: 8 |
| E2-C | MuSiQue | r1 | gemini-3.6-flash | 4/5 (80%) | 0/5 | missing mode name: 4 |
| R1-own | ALFWorld | r1 | qwen3-235b-a22b-2507 | 1/5 (20%) | 0/5 | missing mode name: 1 |
| E2-A | MuSiQue | r1 | qwen3-235b-a22b-2507 | 3/10 (30%) | 0/10 | missing mode name: 3 |
| E2-C | MuSiQue | r1 | qwen3-235b-a22b-2507 | 1/5 (20%) | 0/5 | missing mode name: 1 |
| E2-A | MuSiQue | ww_all | gemini-3.6-flash | 1/10 (10%) | not applicable | step format/range: 1; other: agent outside trace: 1 |
| E2-C | MuSiQue | ww_all | gemini-3.6-flash | 1/5 (20%) | not applicable | step format/range: 1; other: agent outside trace: 1 |
| E2-A | MuSiQue | ww_all | qwen3-235b-a22b-2507 | 0/10 (0%) | not applicable | none |
| E2-C | MuSiQue | ww_all | qwen3-235b-a22b-2507 | 0/5 (0%) | not applicable | none |
| E2-A | MuSiQue | ww_step | gemini-3.6-flash | 4/10 (40%) | not applicable | other: released no-error abstention: 4 |
| E2-A | MuSiQue | ww_step | qwen3-235b-a22b-2507 | 3/10 (30%) | not applicable | other: released no-error abstention: 3 |

All 16 invalid R1 relay outputs omit the mode name. **Step format/range: 0; missing agent: 0; other R1 causes: 0.** In R1’s own examples, the single invalid output also omits its mode name. All seven W&W step-by-step failures are explicit released “no decisive errors found” abstentions, not malformed agent/step fields. They still score wrong for attribution, but are reported as abstentions. Example raw lines: `Error Mode: R.2` (Qwen, E2-C); `Error Mode: C.2` (Gemini, E2-C); `No decisive errors found by step-by-step analysis in file 1.json` (W&W step). Raw file paths, gold/no-gold flags and excerpts are in `baseline_diagnostics.json`.

| R1 E2-A backbone | Technical outputs | Strict agent/stage/family/mode correct | Code-only agent/stage/family/mode correct |
|---|---|---|---|
| gemini-3.6-flash | 10 | 1/10 / 1/10 / 2/10 / 1/10 | 5/10 / 6/10 / 4/10 / 2/10 |
| qwen3-235b-a22b-2507 | 10 | 2/10 / 3/10 / 3/10 / 1/10 | 2/10 / 5/10 / 3/10 / 1/10 |

These scores use known injected targets on all technical items, including ineligible/unkept items; **they are not scientific accuracy estimates**. Family is the card’s primary type score; mode is secondary. Strict versus code-only **changes the apparent comparison**: family attribution changes from Qwen 3/10 vs Gemini 2/10 to Qwen 3/10 vs Gemini 4/10, reversing their ordering. Do not claim a robust model advantage from this pilot. E2-C has no human reference yet, so only validity is reported there.

### Transcript length and renderer diagnosis

Quartiles use the pinned Qwen tokenizer on transcript text only, within each setting; tied lengths stay together, so bins can be uneven or empty. Cells below are strict invalid / outputs, Q1 shortest to Q4 longest. The JSON includes token cutpoints and code-only rates (all zero for R1; unchanged for W&W).

| Setting | Q1 | Q2 | Q3 | Q4 |
|---|---|---|---|---|
| E2-A / r1 / gemini-3.6-flash | 3/4 | 2/2 | 2/2 | 1/2 |
| E2-C / r1 / gemini-3.6-flash | 2/2 | 1/1 | 0/1 | 1/1 |
| R1-own / r1 / qwen3-235b-a22b-2507 | 1/2 | 0/1 | 0/1 | 0/1 |
| E2-A / r1 / qwen3-235b-a22b-2507 | 0/4 | 1/2 | 0/2 | 2/2 |
| E2-C / r1 / qwen3-235b-a22b-2507 | 0/2 | 0/1 | 0/1 | 1/1 |
| E2-A / ww_step / gemini-3.6-flash | 0/4 | 2/2 | 2/2 | 0/2 |
| E2-A / ww_step / qwen3-235b-a22b-2507 | 0/4 | 1/2 | 2/2 | 0/2 |

There is no consistent monotonic length relationship: Qwen E2-C omissions occur in the longest item, whereas Gemini omissions span short and long items; W&W abstentions occur in middle bins and not the longest. Samples of 5–10 outputs are too small to establish independence. Our v1 renderer has contiguous 1-based R1 steps, exact `agent-N`/`aggregator` names, `Step N | Agent: ...` headers and **zero empty steps** in these inputs. W&W receives the same history in its native zero-based order. R1 correctly names agents and in-range steps in every relay output. Its official examples use the native renderer and show the same name-omission defect (1/5), with 1,347–2,387 transcript tokens. **No input-side fault is established, so no renderer change or additional paid renderer pilot was made.** Before/after renderer rates are unchanged because no revised renderer exists; the conditional instruction to repair a proven input issue did not trigger.

## External-method table (written before implementation)

| Method / source | Official assets, licence, pinned revision | Adaptation | Published-number sanity check | Extra effort | Risk |
|---|---|---|---|---:|---|
| W&W all-at-once; E2-C/A/B; [official repository](https://github.com/mingyin1/Agents_Failure_Attribution) | `Automated_FA/Lib/utils.py`; MIT; `b2bae5c5b06d681d04ea5e9b63b7a30525c04925` | Relay → numbered transcript; step → stage; Qwen/Gemini backbone swap; no type output | GPT-4o-mini appears in Figure 3 of arXiv:2505.00212v3; released all-at-once/data numerical sanity run below | 4 h | Medium: preserve official prompt and parsing; renderer changes observation granularity |
| W&W step-by-step; E2-A/B; same source | Same MIT code and pin | Sequential prefixes and stopping rule; same renderer/stage map and model swaps | Not established; do not claim reproduction | 6 h | High weak-baseline risk: 7/20 step-by-step abstentions (Qwen 3/10, Gemini 4/10); no missing-agent or step-format defect; native stopping preserved |
| W&W-Pro [R1] all-at-once; E2-C/A/B; [code](https://github.com/ag2ai/whowhen_pro), [paper](https://arxiv.org/html/2607.09996v2) | `whowhen_eval/prompts.py`; no code licence; `14369dcb079c7cdf86ed2924145d5a28ff5c73b2`; [taxonomy](https://huggingface.co/datasets/Leoxx/whowhen_pro/blob/0bd196c/taxonomy.yaml), CC-BY-4.0, `0bd196c` | Official prompt unchanged; relay RenderResult adapter; step → stage; frozen family/mode maps; Qwen/Gemini swap | Paper reports Gemma 4 but no 31B identifier found. Gemma variant could not be confirmed; structural check, not a numerical reproduction, completed below | 6 h | High weak-baseline risk: strict invalid E2-C 5/10, E2-A 11/20, all missing mode names; code-only 0 invalid. Gemini E2-A 8/10 invalid. Own examples 1/5 invalid. 17 vs 18 modes; unlicensed code kept outside release |
| MAST judge; E2-C/A/B; [official repository](https://github.com/multi-agent-systems-failure-taxonomy/MAST) | `taxonomy_definitions_examples/definitions.txt`, `llm_judge_pipeline.ipynb`; no licence; `a70542e541b2104ef8fcd785778179e173fb8d70` | Transcript renderer; mode → stage/type contingency only; reconcile notebook 3.2/3.3 with definitions; backbone swap | No like-for-like numerical reproduction established | 5 h | High if reduced to a new short prompt. Preserve released pipeline; no invented agent/step scores |
| Our E1 semantic audit; E2-A/B | Local `critical_fact_validation.py`, `alignment.py`; repository LICENSE; record file hashes (working tree is dirty) | Atomic/support-set carrier matcher; no external reimplementation | Existing lexical results are regression checks, not semantic ground truth | 10 h | Author labels required; ontology gaps count as errors |
| Our E6 proxy supports; E2-A/B | Own proposed method, local E6 card; not an external baseline | P-q/P-a; dev choice frozen before held-out; Qwen generator | No published number | 8 h | Both proxy paths technically piloted; dev choice remains unfrozen. No gold-support substitution |
| E3 checkpoint ablation | **Only our own methods**; E3 card and local repair code | Remove checkpoints; identical action hashes required for reuse | Offline regression only | 4 h | No weak external reimplementation risk; route/target consistency risk |
| E6 Part A | **Only our own methods**; E6 card | Gold-free proxy generation and agreement evaluation | No published number | included above | Gold leakage and dev-selection risks |

Pins checked via GitHub API on 2026-11-08; API responses saved in `rebuttal/pilots/20261108_preflight/`. Effort estimates are engineering estimates, not elapsed time.

## E4 donor controls

Original 6/15 matches: nine failures comprise **five shorter controls, three longer controls and one donor with no unused next unit**. Eight of those nine failing pairs have only one eligible donor; the remaining case has two. Examples: repair/control tokens 65/58 (10.8% short), 49/66 (34.7% long), 33/0 (no next unit). Donor eligibility is preserved: other board agents, prefer support-free agents, existing fallback when none are support-free. No eligibility is inferred from an answer outcome.

Proposed clarification: among eligible donors, prefer the same added-unit count, then the closest exact-base-token total; break ties by SHA-256 of `[42, instance_id, arm, donor_agent]`. Keep the original next-unit score order and verbatim-source-span rule. Do not pad, shorten, change the ±10% rule, or call a mismatched pair matched. This is **planned, pending author confirmation** for the full run.

The requested same-ID technical re-pilot is complete: **7/15 matched**, up from 6/15. One extraction control changes from 74/64 to 74/79 tokens; the other eight failures remain. All three controls on each of five reserved items were re-evaluated; identical outcomes were reused. Only **2 new calls**, **$0.000231**, **4.30 API seconds** were needed. Each donor/action choice was saved before the new answer. Changed-source fidelity remains an author check; E4 stays FIX. Artifacts: `20261108_e4_donor_v2/`.

## E2-A kept-injection yield

The $22.70 measured projection is a **200-candidate technical workload**, not 200 kept injections; it runs baselines even for unkept cases. For the yield calculation only, assume 50 candidates per fault type (not a changed config). The pilot is too small and lacks author screening/postchecks, so it cannot establish human-qualified yield.

| Fault type | Pilot candidates | Original provisional keep | Conservative single-defect pass | Projected pass / 50 candidates | Human-qualified kept yield |
|---|---|---|---|---|---|
| extraction_omission | 2 | 1/2 | 0/2 | 0 | not estimable; human checks absent |
| selection_omission | 1 | 0/1 | 0/1 | 0 | not estimable; human checks absent |
| distortion | 1 | 0/1 | 0/1 | 0 | not estimable; human checks absent |
| aggregation | 1 | 0/1 | 0/1 | 0 | not estimable; human checks absent |

The original extraction rate was 1/2, which would suggest 25/50 candidates; its postcheck shows additional missing facts, so it is not a single-defect keep. The conservative technical point projection is therefore 0 for each type, **not evidence that the true human-screened yield is zero**. With only 0/2 or 0/1, Wilson 95% upper rates are about 66%/79% (33/40 per 50 candidates). “Up to 30 per fault type” is a cap, not a demonstrated attainable yield. Aggregation additionally awaits the human visible-step check. A code-review fix accepts the actual `extraction_omission`/`selection_omission` names in the keep predicate; raw outputs were not changed.

## Approved seed 43 and updated budgets

Seed 43 is **on** in `rebuttal/configs/E4-P-full.json`; pilot configs are unchanged. This is a planning config, not authorisation to execute a full run now. Seed-43 outcomes are clustered by underlying task across seeds. The one-item pilot is discarded for final inference and the full run makes fresh calls. Option (b) remains dropped because the paper has no second benchmark with established extraction and distortion groups.

| Experiment | Planned calls | Planned USD | Pilot-projected calls | Pilot-projected USD | Annotation h |
|---|---|---|---|---|---|
| E1 | 1,976 | $1.27 | 1,976 | $0.61 | 112 |
| E4 | 7,668 | $4.39 | 7,753 | $2.09 | 8 |
| E4-P | 9,480 | $12.35 | 8,969 | $5.36 | 4 |
| E2-C | 72 | $0.14 | 72 | $0.52 | 0 |
| E2-A | 5,230 | $9.61 | 6,200 | $22.70 | 30 |
| **Batch 1** | **24,426** | **$27.77** | **24,970** | **$31.28** | **154 h; ≈9 days** |

The technical E6 proxy supplement adds 1,400 projected calls / $0.46 for 200 candidates: total **26,370 / $31.74** including it. E4-P includes the approved 78 extra seed-43 traces: planned 4,368 calls / $5.59 / 4 h; one-item measured projection 4,368 calls / $2.41. Expected added groups remain cache projections (extraction ≈16, selection ≈40, aggregation ≈12, strict distortion ≈0–1), not new-seed outcomes.

Prices: OpenRouter route, [saved provider metadata](https://openrouter.ai/api/v1/models), checked 2026-11-08. Input/output USD per million: Qwen 0.14/0.80, GPT-4o-mini 0.15/0.60, Gemma 0.20/0.40, Gemini 0.75/3.75. Planned estimates assume 70/30 input/output and 2k tokens per baseline/judge call, original cohort weights 300 MQ/63 SB5/63 SB10. Measured projections use actual ledger token/call mix; E1’s 152 GPT prerequisites remain an explicit $0.04 estimate. E2-A’s plan assumes about 120 kept injections, whereas its technical projection spends on all 200 candidates. Thus the cost columns are workload scenarios, not like-for-like expected efficacy budgets. Screening, retries, new source populations and changed E1 design can add work. No unapproved E1 enlargement is included. Calculators: `recompute_costs.py`, `scripts/project_batch1_costs.py`.

## Final external sanity checks

**[R1]: structural check, not a numerical reproduction.** The Gemma variant could not be confirmed as Gemma-4-31B. Five own ALFWorld traces, Qwen-235B, released prompt/taxonomy unchanged: 5/5 agent-step-mode parses, 5/5 in-range steps, 5/5 valid codes, 4/5 valid code+name pairs. Parse-failure rate 0%; strict invalidity 20% due to one missing name.

**Who&When finished: 368/368 conditions**, 184 released native traces × with/without gold, GPT-4o-mini, pinned released all-at-once code. PID 73598 exited; no second worker was started. Native released-evaluator pooled agent accuracy **52.45%**, step **8.42%**; parse success **100%**. Strict-equality sensitivity: agent **52.45%**, step **6.52%**.

| System | Gold answer | Agent accuracy | Step accuracy | N |
|---|---|---|---|---|
| Algorithm-Generated | False | 51.59% | 8.73% | 126 |
| Hand-Crafted | False | 58.62% | 10.34% | 58 |
| Algorithm-Generated | True | 47.62% | 8.73% | 126 |
| Hand-Crafted | True | 58.62% | 5.17% | 58 |

Against [Who&When, arXiv:2505.00212v3](https://arxiv.org/abs/2505.00212), Figure 3’s approximate 55% agent / 4% step values, pooled differences are **-2.55 / +4.42 percentage points**. This is a numerical sanity reproduction attempt, not exact agreement. The radar chart lacks exact numeric labels (visual reading roughly ±2 points); OpenRouter versus historical Azure deployment, unknown historical model revision and ambiguous figure aggregation limit comparison. The native evaluator uses substring matching; exact step equality drops the measured step rate to 6.52%. Equal weighting of the four system/gold cells gives 54.11% agent / 8.24% step, further showing aggregation sensitivity.

## Annotation and verification

Annotation packages remain under `rebuttal/annotation/`: E1 reach/fidelity; nonblind E2-A author screening and postchecks; E4 40 matcher spot checks and swaps; blind E2-B guidelines for batch 2. Each includes a schema, five synthetic worked examples and sheets. Five disjoint calibration source traces exist; **human calibration has not happened**, so no human agreement is claimed. Provisional pilot labels/baseline outputs never enter annotator sheets.

E1 A+B / C+D rotate by instance, with the complementary pair assigned to blind Part B. Recursive allowlist export hides all audit, matcher, lexical and baseline outputs. Current main-study hours per annotator: E1 28, E2-A 7.5, E4 2, approved seed spot checks 1 = 38.5; Part B later 17.5; calibration reserve 2.1 extra. Human calibration statistics remain κ for E1 presence/fidelity/binary, E2-A eligibility/keep, E4 fidelity/swap validity, and Part B class/reference.

Full `.conda-env/bin/python -m pytest -q`: **283 passed** (`20261108_review3/pytest.log`). Added checks cover weighted estimators, stratified instance bootstrap, fixed SHA lists/weights, partial sensitivity and all-trace rate denominator, strict/code-only scoring, W&W abstention, donor tie-breaking, omission-name keep gates and full/pilot config isolation.

## Settings changes for approval

| Proposed setting | Status and plain-language change |
|---|---|
| E1 primary unit and draw | **Planned, pending author confirmation:** make fact-level presence/fidelity primary, keep trace-level binary secondary; use the specified lexical τ = 0.5 stratified held-out draw and inverse-probability weights. Sizes 80/100 are alternatives only; none currently meets the fidelity precision goal. |
| Partial-as-lost sensitivity | **Planned, pending author confirmation:** primary binary excludes partial/uncertain; an additional analysis counts partial as lost while still excluding uncertain. |
| R1 scoring | **Planned, pending author confirmation:** strict primary counts invalid output wrong; code-only sensitivity accepts a valid code without its name, preserving valid agent/step requirements. Report changes in conclusions. |
| E4 donor selection | **Planned, pending author confirmation:** among eligible donors choose the closest token total with matching unit count and fixed SHA tie-break, replacing “first other agent”; retain ±10%. Reserved technical re-pilot completed. |
| Renderer | No change proposed: no input-side defect established. Any future renderer change remains **planned, pending author confirmation** until specified, versioned and re-piloted. |

The old CI thresholds are removed, not held for approval. Seed 43 is approved and enabled, not a hold. Exact tokenizers and the R1 structural check are completed implementation, not holds.

## Author decisions and recommended defaults

Keep D1 = A and D11 = A. Confirm Plan A and its estimands/weights before labelling or freezing; do not enlarge to a size that does not meet the stated fidelity precision goal. Keep strict baseline scores primary and show code-only sensitivity prominently; do not infer superiority from the invalid-output burden. Keep E4 FIX while controls remain unmatched; do not relax token tolerance. Treat 30 injections per fault type as an unverified cap until human screening and single-defect checks establish yield. No full runs are authorised by this report.

## Appendix A — raw examples and measured pilot inventory

Examples retain fixed filename-hash order, not selected by failure class. Full raw files are unchanged; snippets are truncated for readability.

### e1_v2

| Raw file | Excerpt |
|---|---|
| rebuttal/pilots/20261108_e1_v2/matcher/095ad327fe4333ff0bae9bdc088b03c9c75680935166c13eb5a259f35e806c6e.json | {"facts": [{"board": [{"fidelity": "faithful", "role": "sole", "unit_ids": ["pool:a1:u0"]}], "extraction": [{"fidelity": "faithful", "role": "sole", "unit_ids": ["pool:a1:u0"]}], "fact_id": "f1"}, {"board": [{"fidelity": "faithful", "role": "sole", "unit_ids": |
| rebuttal/pilots/20261108_e1_v2/matcher/097b81ab935df9d4a061838e851f65c92124027bc1f8cb93c9c27f69ff1f7b43.json | {"facts": [{"board": [{"fidelity": "distorted", "role": "sole", "unit_ids": ["pool:a0:u1"]}], "extraction": [{"fidelity": "faithful", "role": "sole", "unit_ids": ["pool:a0:u0"]}], "fact_id": "f1"}, {"board": [], "extraction": [{"fidelity": "faithful", "role":  |

### e4_technical

| Raw file | Excerpt |
|---|---|
| rebuttal/pilots/20261108_e4_technical/raw/26e9a63ebc1d0b7e498d19fc3d7e2f4e853c19b5c62335d2dd608c7c47680232.json | ANSWER: Ahinoam   USED_EVIDENCE: 1, 1   RATIONALE: The evidence states that Ahinoam is the wife of Saul, who is identified as the first king of Israel. |
| rebuttal/pilots/20261108_e4_technical/raw/3df6a80e61502fd184f78f0d76599a73a32c4a8782534ac196d7f1a35ffd7c1c.json | ANSWER: Insufficient information.   USED_EVIDENCE:   RATIONALE: The provided evidence units confirm that the Carolina Hurricanes are part of the NHL, but neither unit specifies when the NHL regular season begins. |

### e4_p_technical

| Raw file | Excerpt |
|---|---|
| rebuttal/pilots/20261108_e4_p_technical/raw/26e9a63ebc1d0b7e498d19fc3d7e2f4e853c19b5c62335d2dd608c7c47680232.json | ANSWER: Ahinoam   USED_EVIDENCE: 1, 1   RATIONALE: The evidence states that Ahinoam is the wife of Saul, who is identified as the first king of Israel. |
| rebuttal/pilots/20261108_e4_p_technical/raw/3df6a80e61502fd184f78f0d76599a73a32c4a8782534ac196d7f1a35ffd7c1c.json | ANSWER: October 4, 2017   USED_EVIDENCE: 1, 1   RATIONALE: The Carolina Hurricanes belong to the NHL, and the 2017–18 NHL regular season began on October 4, 2017, as stated in the evidence. |

### e2_c_technical

| Raw file | Excerpt |
|---|---|
| rebuttal/pilots/20261108_e2_c_technical/raw/097b81ab935df9d4a061838e851f65c92124027bc1f8cb93c9c27f69ff1f7b43.json | Agent Name: agent-1   Step Number: 1   Reason for Mistake: The Minikahda Club is located in Minneapolis, Minnesota, which lies near **Lake Calhoun** (now officially Bde Maka Ska), a freshwater lake that is part of the Mississippi River watershed—not connected  |
| rebuttal/pilots/20261108_e2_c_technical/raw/11a96876848b74164948781df432837322bd4c2b0924a074134eb7511b6bac21.json | Agent Name: agent-1   Step Number: 1   Reason for Mistake: The error lies in agent-1's claim that "The song 'Good Little Girls' was written by Troy Seals and Brett Jones." This statement is factually incorrect and introduces misleading information. "Good Littl |

### e2_a_technical

| Raw file | Excerpt |
|---|---|
| rebuttal/pilots/20261108_e2_a_technical/raw/097b81ab935df9d4a061838e851f65c92124027bc1f8cb93c9c27f69ff1f7b43.json | ANSWER: Insufficient information. USED_EVIDENCE:  RATIONALE: The evidence provided does not specify the location of the Minikahda Club or the relevant treaty that ceded territory extending west to a body of water near it. / ANSWER: Insufficient information. US |
| rebuttal/pilots/20261108_e2_a_technical/raw/11a96876848b74164948781df432837322bd4c2b0924a074134eb7511b6bac21.json | ANSWER: Insufficient information.   USED_EVIDENCE: 1, 1   RATIONALE: The evidence units provide information about the song "Good Little Girls" and its chart performance, as well as identifying Blue County as the duo that recorded it, but they do not list any i |

| Job | Calls | USD | Summed API seconds | Per item: calls/USD/API seconds |
|---|---|---|---|---|
| e1_v2 | 60 | $0.018822 | 263.5 | 2.00 / $0.000627 / 8.78s |
| e4_technical | 91 | $0.024564 | 263.3 | 18.20 / $0.004913 / 52.66s |
| e4_p_technical | 54 | $0.034652 | 107.0 | 10.80 / $0.006930 / 21.40s |
| e2_c_technical | 30 | $0.217669 | 316.2 | 6.00 / $0.043534 / 63.25s |
| e2_a_technical | 155 | $0.567509 | 900.1 | 31.00 / $0.113502 / 180.02s |
| e2_a_proxy | 35 | $0.011430 | 156.9 | 7.00 / $0.002286 / 31.38s |
| e4_p_seed43 | 56 | $0.030872 | 191.6 | 56.00 / $0.030872 / 191.55s |
| r1_structural | 5 | $0.002672 | 16.8 | 1.00 / $0.000534 / 3.36s |
| ww_sanity | 368 | $0.446887 | 1322.7 | 1.00 / $0.001214 / 3.59s |

No API timeout/error was logged; no provider safety-refusal finish reason was recorded. Missing attribution fields and abstentions are reported above. API seconds sum request latency, not wall time. E4 donor re-pilot is separately costed above. E1 legacy source generation and calibration cost $0.022344 and $0.013231; they are not charged again in projections.

## Appendix B — preregistration hashes

Updated E1 and scoring/donor designs are proposals/technical supplements. Historical files are explicitly archived; old call ledgers remain bound to the exact original hash and are not rewritten.

| File under `rebuttal/pilots/prereg/` | SHA-256 |
|---|---|
| Baseline-scoring-v3.md | ef127878bf74b208639ad7de7b6f6fa32de85820556c3d9a449d5f4de3093982 |
| E1-pre-interval-archived.md | e13f169dac6c252a2b9a5fcff7227139a552fc7fb252d3e55d4c7abe17c0bb07 |
| E1-v1.md | 90e7f359b846a1fb64bd1df8df3caf0bbd959732a78bd165efb027867138896e |
| E1-v2.md | f75782e3090726b0b2b7ad620bfee2ac1394903e61712449a89690d7c0c811d9 |
| E1.md | e736a5227a271b776bf1af19a70440e8e327f2d767e472e25e1048b5a039f07d |
| E2-A-proxy.md | 08a21f2f11e95b9f6eaaf2a7429252f38b73a8d5d03361b6df054095a248f4f1 |
| E2-A-technical.md | 490e7864b109999de5c4e49aec2987115cf9695d3fc1324b135f6aa98dbb8b81 |
| E2-A.md | 2cc504c972955193cf107b33c192ad6352e8860424ba0b892d5d8880e48adcc7 |
| E2-C-technical.md | 131904da4856fe6295243cac824c7624a57c9aa98f06c17d5abc7cb0168ad241 |
| E2-C.md | e8ef11d946ffd1b2c7f0d17c20b5bd5a101ba28310a4cc7d10b67d8fc45db8bc |
| E4-P-full-seed43.md | 18e65d9a38c0059604e43fa85255c7531360462ac4a8017342ddd759617b634e |
| E4-P-seed43.md | 01d93bc6c4432e3afb2f40ad42d55e3573dd32c704ff8892d27d87b5b4f03ba6 |
| E4-P-technical.md | bf2b19cd257fba8d86d0dcbd836c1641c1e2837f1e1ed64323273f85af5828e3 |
| E4-P.md | 49f3a0369da22b8024dcae84a4e3ce181ca8e0db2bd8c2fa23fb2ab40cea9a66 |
| E4-donor-v2.md | 0600492bf9a3435a441f64a9d1ad7a76534966286a33b9ae8573e5db30dcc73d |
| E4-technical.md | 33c38be896c7ed91f841e913501b44f5aae1316c354cb7b2f207a625b8cd5985 |
| E4.md | dccedd654200945699912ed7a7e0fa9166742e47641cf6cbc3e90f3cac2189e4 |
| R1-structural.md | 547c570dacc847a1cb0dcf4b23bb4e01bdc8bf1b55add90f5c610bcec77bf08a |
| WW-sanity.md | b9c1edbc53af64fe1243c4962c982eecf41d90c1236986ea1afeb2817832778e |

## Appendix C — jobs and logs

All listed jobs have finished at this snapshot. Detached workers used exclusive locks, cumulative caps and append-only intent/result ledgers; no duplicate worker was started for Who&When. The no-API interval simulation was corrected before its results were used; superseded PID 79594 was stopped, corrected PID 81970 completed.

| Job | PID (historical) | Command | Log |
|---|---|---|---|
| e1_v2 | 26964 | .conda-env/bin/python -u -m scripts.pilot_e1_v2 --execute --max-calls 180 | rebuttal/pilots/20261108_e1_v2/run.log |
| e4_technical | 68168 | .conda-env/bin/python -u -m scripts.pilot_e4 --config rebuttal/pilots/configs/E4-technical.json --execute --max-calls 130 | rebuttal/pilots/20261108_e4_technical/run.log |
| e4_p_technical | 12375 | .conda-env/bin/python -u -m scripts.pilot_e4p --config rebuttal/pilots/configs/E4-P-technical.json --execute --max-calls 60 | rebuttal/pilots/20261108_e4_p_technical/run.log |
| e2_c_technical | 68169 | .conda-env/bin/python -u -m scripts.pilot_e2c --config rebuttal/pilots/configs/E2-C-technical.json --execute --max-calls 30 | rebuttal/pilots/20261108_e2_c_technical/run.log |
| e2_a_technical | 68170 | .conda-env/bin/python -u -m scripts.pilot_e2a --config rebuttal/pilots/configs/E2-A-technical.json --execute --max-calls 260 | rebuttal/pilots/20261108_e2_a_technical/run.log |
| e2_a_proxy | 36019 | .conda-env/bin/python -u -m scripts.pilot_e2a_proxy --execute --max-calls 75 | rebuttal/pilots/20261108_e2_a_proxy/run.log |
| e4_p_seed43 | 82660 | .conda-env/bin/python -u -m scripts.pilot_e4p_extra_seed --execute --max-calls 60 | rebuttal/pilots/20261108_e4_p_seed43/run.log |
| r1_structural | 39350 | .conda-env/bin/python -u -m scripts.check_r1_structure --execute --max-calls 5 | rebuttal/pilots/20261108_r1_structural/run.log |
| ww_sanity | 73598 | .conda-env/bin/python -u -m scripts.reproduce_whowhen --execute --max-calls 368 | rebuttal/pilots/20261108_ww_sanity/run.log |
| e4_donor_v2 | 91549 | .conda-env/bin/python -u -m scripts.pilot_e4_donor_v2 --execute --max-calls 21 | rebuttal/pilots/20261108_e4_donor_v2/run.log |
| E1 width simulation | 81970 | .conda-env/bin/python -u -m scripts.simulate_e1_interval_width | rebuttal/pilots/20261108_review3/interval_width_v2.log |

Refresh read-only diagnostics and report with `python -m scripts.diagnose_batch1_baselines`, `python -m scripts.summarize_batch1_v2`, `python -m scripts.project_batch1_costs`, then `python -m scripts.write_batch1_report_v3`. Do not rerun paid jobs merely to refresh the report.
