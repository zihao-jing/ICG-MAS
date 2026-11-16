# Evidence-Flow Audit for Multi-Agent LLM Systems

Code and experiment archive for *“Where Does Reasoning Fail? Attributing Distributed LLM Failures through Critical Evidence.”*

## What this release contains

This is the anonymous code release for the submission. It contains the code and short records of every experiment behind the reported numbers; manuscripts, raw API logs and model traces are not included.

| Path | Contents |
|---|---|
| `src/` | Protocols, data loaders, evaluation and the evidence-flow audit |
| `utility/` | API adapters (OpenRouter is the primary interface) and figure scripts |
| `scripts/` | Experiment runners and analysis scripts; each script's docstring gives its command and output folder |
| `tests/` | Offline unit tests (no API keys, no network) |
| `rebuttal/pilots/` | One folder per experiment: its frozen rule, prompts, `report.md` and `score*.json` |
| `rebuttal/pilots/prereg/` | Rules and prompts written and hashed before each run |
| `iclr2027_paper/experiments/repair/` | Reviewed cohorts, decisions and summaries of the repair studies |
| `data/` | Silo-Bench benchmark files; the MuSiQue dev split is downloaded separately |

**Not included, by design.** Raw API call logs (`calls.jsonl`), full model traces, cached baseline runs (`results/`), author annotation packets and the manuscript sources stay local because of size or because they contain author-written material. Every report names the files it was computed from, so the numbers can be traced; re-running a script regenerates its traces and call log in a fresh output folder.

**Anonymity.** Personal names, local paths and account identifiers have been removed. API keys are read from the environment or a local `.env`, which is ignored by Git.

### Where the reported numbers come from

| Result | Experiment record (`rebuttal/pilots/…`) |
|---|---|
| Coverage label validation (MuSiQue, Silo-Bench) | `20261113_label_validation_v9/`, `20261113_sb_presence_validation/` |
| MuSiQue trace outcomes (fact lost vs. all facts arrived) | `20261113_musique_presence_full/` |
| Comparison with Who&When and Who&When Pro | `20261115_final_comparison/`, `20261116_stage_naming/` |
| Distortion rate and restore test | `20261115_relay_v2_rescore/`, `20261116_restore_judges_sonnet_opus/`, `20261116_restore_equiv_gemini/` |
| Redundancy injection (one, two, three slots) | `20261115_redundancy_k1/`, `20261115_redundancy_injection/`, `20261115_redundancy_k3/` |
| Targeted repairs | `20261116_f38_repairs/`, `20261116_agg_repair_equiv/` |
| Checkpoint necessity | `20261114_e3_full/`, `20261115_e3_sb_routing_validated/` |
| Run-time audit with model-written facts | `20261115_mq_hop_reconcile/`, `20261115_proxy_support_89/` |

Run commands below from the repository root. Python scripts are invoked as modules so repository imports resolve consistently. Tests are offline; experiment runners, including their `--test` mode, make paid API calls.

---

## Overview

Multi-agent LLM systems increasingly split a task across collaborating sub-agents, and many failures arise in that collaboration, where final accuracy cannot locate them. The **evidence-flow audit** follows each answer-critical fact through five stages (sharding, extraction, transmission, consolidation and aggregation) and reports both the failure mode and the fact that was lost.

| Failure mode | Definition |
|---|---|
| **Extraction loss** | An agent holds the fact but does not extract it |
| **Evidence distortion** | The fact is relayed with its meaning changed |
| **Redundancy waste** | Duplicates take message slots that a needed fact would otherwise fill |
| **Aggregation failure** | Every critical fact reaches the final step, yet the answer is wrong |

Fact coverage at each checkpoint is labelled by an LLM (Claude Haiku 5.5) validated against an independent model (Gemini 3.6 Flash); the earlier word-matching rule is kept for comparison.

---

## Framework

### Evidence-Flow Pipeline

```
Private Shard → [Extract] → Evidence Units → [Score] → [Select/Relay] → Evidence Board → [Aggregate] → Answer
                                                                            ↑
                                                                      Audit Point
```

Each atomic evidence unit is assigned a `source` tag as it moves through the pipeline:
`raw_shard` → `extracted_unit` → `transmitted_message` → `aggregator_input` → `final_rationale`

### Audit Metrics

| Metric | Formula | Interpretation |
|---|---|---|
| **Critical Evidence Recall** | \|S\* matched in board\| / \|S\*\| | How much of the gold-critical evidence survives transmission |
| **Omission Rate** | 1 − Recall | Fraction of critical units that never reach the evidence board |
| **Distortion Rate** | Distorted critical / Transmitted critical | Fraction of transmitted critical units with altered meaning |
| **Redundancy Rate** | Mean pairwise similarity of transmitted units | How much budget is wasted on duplicates |
| **Useful Budget Share** | Critical units / Transmitted units | Fraction of the budget carrying critical information |
| **Aggregation Failure** | Evidence present ∧ answer wrong | Failure to synthesize available evidence |

### Alignment Labels

Transmitted units are aligned to gold critical units by an LLM judge:

| Label | Meaning |
|---|---|
| `EXACT` | Identical meaning and all key entities/numbers |
| `PARAPHRASE` | Same meaning, different wording |
| `PARTIAL` | Key constraint omitted |
| `DISTORTED` | Key entity, number, or relation changed |
| `NO_MATCH` | Unrelated to the gold unit |

---

## Communication Protocols

| Protocol | Category | Description |
|---|---|---|
| `single_local` | No-comm | Each agent answers from its private shard only |
| `majority_vote` | No-comm | Majority vote over isolated answers |
| `best_local` | No-comm | Oracle upper bound for isolated agents |
| `full_sharing` | Baseline | All agents share their full evidence |
| `free_form_debate` | Baseline | Iterative answer exchange and revision |
| `summary_exchange` | Baseline | Agents send natural-language summaries |
| `confidence_gated` | Baseline | Share only when self-assessed confidence is low |
| `disagreement_gated` | Baseline | Share only when answers diverge |
| `random_relay` | Relay | Extract units, select uniformly at random |
| `score_ranked_relay` | Relay | Select by local importance score (relevance × uniqueness × criticality) |
| `redundancy_aware_relay` | Relay | Score-ranked selection with redundancy penalty ρ |

The **redundancy-aware relay** is the primary proposed protocol: it scores each extracted unit by a composite local importance score and applies a redundancy penalty to diversify the transmitted set.

---

## Directory Structure

```
.
├── src/
│   ├── eval/
│   │   ├── run_experiment.py       # Main protocol runner (Table 1)
│   │   ├── ablation_study.py       # Protocol ablation study (Table 2)
│   │   ├── bottleneck_analysis.py  # Critical evidence bottleneck (Table 3)
│   │   ├── data_loader.py          # MuSiQue loader + sharding
│   │   ├── silo_bench_loader.py    # Silo-Bench loader
│   │   ├── evaluate.py             # F1, majority vote, exact match
│   │   ├── metrics.py              # Recovery, utility, evidence coverage
│   │   ├── compute_metrics.py      # Post-hoc ROUGE/BLEU/BERTScore
│   │   ├── variant_a.py            # Distributed isolated evaluation
│   │   └── variant_b.py            # Centralized single-agent baseline
│   ├── protocols/
│   │   ├── base.py                 # AgentShard, ProtocolResult, shared helpers
│   │   ├── local.py                # No-comm baselines
│   │   ├── full_sharing.py         # Full evidence sharing
│   │   ├── relay.py                # Random / score-ranked / redundancy-aware relay
│   │   ├── summary_exchange.py     # Summary exchange
│   │   ├── gated.py                # Confidence- and disagreement-gated
│   │   └── debate.py               # Free-form debate
│   └── audit/
│       ├── evidence_units.py       # EvidenceUnit dataclass, gold support loader, extraction
│       ├── alignment.py            # LLM-judge alignment (EXACT/PARAPHRASE/PARTIAL/DISTORTED)
│       ├── metrics.py              # Omission, distortion, redundancy, aggregation-failure metrics
│       ├── interventions.py        # Controlled evidence deletion experiments
│       ├── local_importance_analysis.py  # LOO importance vs. true criticality (Table 4)
│       └── reporting.py            # JSONL and LaTeX export
├── utility/
│   ├── apis/
│   │   ├── base.py                 # Unified APIRequest / APIResponse types
│   │   ├── openrouter_api.py       # Primary interface (200+ models via OpenRouter)
│   │   ├── claude_api.py           # Anthropic direct adapter
│   │   ├── openai_api.py           # OpenAI direct adapter
│   │   └── gemini_api.py           # Google Gemini adapter
│   └── figures/
│       ├── polar_local_importance.py  # Polar chart: local importance AUC (Table 4)
│       └── polar_round_4.py           # Polar chart: round-4 evidence flow
├── scripts/                        # Experiment runners and analysis scripts
│   ├── run_evidence_flow_audit.py  # Full evidence-flow audit experiment
│   ├── compute_audit_metrics.py    # Compute omission/distortion metrics for a run dir
│   ├── local_importance_analysis.py
│   ├── local_importance_multimodel.py
│   ├── local_importance_musique.py
│   ├── exp1_hop_stratification.py
│   ├── exp2_extraction_quality.py
│   ├── exp3_oracle_relay.py
│   ├── exp4_k_sweep.py
│   └── ...                         # Additional analysis scripts
├── tests/                          # Unit tests (fully mocked, no API keys required)
├── data/
│   ├── musique_100_ids.json        # Sampled MuSiQue instance IDs
│   └── silo-bench/                 # Silo-Bench benchmark files and generator
├── run.sh                          # Activates conda env and loads .env
└── requirements.txt
```

> **Data note:** The MuSiQue dev split must be downloaded separately and placed at
> `data/musique/musique_ans_v1.0_dev.jsonl`.

---

## Setup

```bash
conda create -n ef-audit python=3.11
conda activate ef-audit
pip install -r requirements.txt

# Set API key (OpenRouter is the primary interface)
export OPENROUTER_API_KEY="your-key-here"
```

Or create `.env` in the repository root (ignored by Git):

```bash
OPENROUTER_API_KEY=your-key-here
```

Use `run.sh` to load `.env` and select `.conda-env`, an active environment, or the `ef-audit` conda environment, in that order:

```bash
./run.sh python -m src.eval.run_experiment --help
```

---

## Running Experiments

### Table 1 — Protocol comparison

```bash
# Silo-Bench, n=5 agents, all protocols
./run.sh python -m src.eval.run_experiment \
  --dataset silobench \
  --n-agents 5 \
  --protocols all \
  --model deepseek/deepseek-v4-flash \
  --limit 100 \
  --output results/run_silo_n5

# MuSiQue, n=5 agents
./run.sh python -m src.eval.run_experiment \
  --dataset musique \
  --data data/musique/musique_ans_v1.0_dev.jsonl \
  --n-agents 5 \
  --protocols all \
  --model openai/gpt-4.1-mini \
  --limit 100 \
  --output results/run_musique_n5
```

### Table 2 — Protocol ablation

```bash
./run.sh python -m src.eval.ablation_study \
  --model deepseek/deepseek-v4-flash \
  --output results/ablation
```

### Table 3 — Critical evidence bottleneck

```bash
./run.sh python -m src.eval.bottleneck_analysis \
  --model deepseek/deepseek-v4-flash \
  --n-agents 5 \
  --output results/bottleneck_n5
```

### Full evidence-flow audit

```bash
# Runs all protocols and logs full audit data (shards, extracted units,
# transmitted units, alignments, omission/distortion metrics)
./run.sh python -m scripts.run_evidence_flow_audit \
  --benchmark silo_bench \
  --num-agents 5 \
  --protocols all \
  --model deepseek/deepseek-v4-flash \
  --output-dir outputs/audit_run \
  --limit 50

# Include intervention experiments (deletion curves) and LOO local importance
./run.sh python -m scripts.run_evidence_flow_audit \
  --benchmark musique \
  --num-agents 5 \
  --run-deletions \
  --run-local-importance \
  --model openai/gpt-4.1-mini \
  --output-dir outputs/audit_musique
```

### Compute audit metrics for an existing run

```bash
./run.sh python -m scripts.compute_audit_metrics \
  --run-dir results/run_silo_n5 \
  --summary-exchange
```

### Validate critical-fact tracking from cached traces

This offline workflow makes no API
calls and never overwrites existing run artifacts. Export one condition at a
time (e.g. score-ranked relay and summary exchange on each benchmark), fill the
atomic-fact sheet, then give identical label templates to two annotators.

```bash
# 1) Export a balanced correct/error MuSiQue relay sample and an empty fact sheet.
./run.sh python -m scripts.validate_critical_fact_tracking export \
  --dataset musique --run-dir results/run_qwen235b_musique \
  --protocol score_ranked_relay --source-id mq_score_relay \
  --sample-size 40 --seed 42 \
  --traces-out validation/mq_relay_traces.jsonl \
  --facts-out validation/mq_relay_facts.jsonl

# 2) After atomizing and checking the supports in mq_relay_facts.jsonl,
# create a blinded checkpoint-label file; copy it once per annotator.
./run.sh python -m scripts.validate_critical_fact_tracking label-template \
  --traces validation/mq_relay_traces.jsonl \
  --facts validation/mq_relay_facts.jsonl \
  --output validation/mq_relay_labels.jsonl

# 3) Merge completed independent labels, adjudicate records with final_label=null,
# then recompute semantic recall, complete-support coverage, matcher error, and diagnoses.
./run.sh python -m scripts.validate_critical_fact_tracking adjudicate \
  --annotator-a validation/mq_relay_annotator_a.jsonl \
  --annotator-b validation/mq_relay_annotator_b.jsonl \
  --output validation/mq_relay_adjudication.jsonl \
  --agreement-out validation/mq_relay_agreement.json
./run.sh python -m scripts.validate_critical_fact_tracking analyze \
  --traces validation/mq_relay_traces.jsonl \
  --facts validation/mq_relay_facts.jsonl \
  --adjudicated validation/mq_relay_adjudication.jsonl \
  --output validation/mq_relay_report.json
```

### CLI Arguments (run_experiment.py)

| Argument | Default | Description |
|---|---|---|
| `--data` | MuSiQue dev split | Path to JSONL benchmark |
| `--dataset` | `silobench` | `musique` or `silobench` |
| `--model` | `deepseek/deepseek-v4-flash` | Model string (OpenRouter format) |
| `--n-agents` | dataset-dependent | Silo-Bench count filter; MuSiQue shard count |
| `--protocols` | `all` | Comma-separated protocol names, or `all` |
| `--max-states` | `3` | Max evidence units extracted per agent |
| `--max-tokens` | `1024` | Per-call output token budget |
| `--max-workers` | `128` | API concurrency |
| `--limit` | `0` (no limit) | Cap on instances |
| `--seed` | `42` | Random seed |
| `--output` | `results/run_<timestamp>/` | Output directory |
| `--test` | `False` | Five-instance run; still calls the API |

---

## Historical model identifiers (via OpenRouter)

These are identifiers used or configured in this workspace, not a current availability guarantee. Check the provider before a new run and record the exact identifier.

```python
# OpenAI
"openai/gpt-4.1-mini"
"openai/gpt-4.1"

# Anthropic
"anthropic/claude-3.5-haiku"
"anthropic/claude-sonnet-4-6"

# Google
"google/gemini-2.0-flash-001"
"google/gemini-2.5-flash-preview"

# DeepSeek
"deepseek/deepseek-v4-flash"

# Mistral
"mistralai/mistral-small"

# Qwen
"qwen/qwen3-235b-a22b"
"qwen/qwen3-8b"
```

---

## Output files

The main protocol runner writes `results.json` and `per_instance_results.jsonl`
inside `--output`. Its aggregate rows are under `results["table"]`; use the
saved arguments and per-instance records when comparing runs. Other runners
have their own schemas: frozen repair writes `plan.json`, API logs,
`per_instance_results.jsonl`, and `summary.json`. Audit metrics are separate
analysis products, not guaranteed outputs of every runner.

Historical ablation files use `csc_topk` for score-ranked relay and
`csc_redundancy` for redundancy-aware relay. Printed tables use the current
names; do not count the old and new names as separate protocols.

---

## Tests

```bash
# All tests — no API keys required (fully mocked)
./run.sh python -m pytest tests/ -v

# Specific module
./run.sh python -m pytest tests/test_protocols.py -v
```

---

## Benchmarks

| Benchmark | Type | Role |
|---|---|---|
| **Sharded MuSiQue** | Multi-hop QA (2–4 hops), paragraphs distributed across agents | Primary evaluation; gold supporting-paragraph labels available |
| **Silo-Bench** | Hidden-profile tasks with information silos | Secondary evaluation; tests generalization across task structures |
