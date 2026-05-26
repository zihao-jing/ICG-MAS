# Evidence-Flow Audit for Multi-Agent LLM Systems

Code repository for the paper *"Evidence-Flow Audit for Multi-Agent LLM Systems"*.

---

## Overview

Multi-agent LLM systems share information through communication protocols, but existing evaluations measure only final accuracy — they cannot tell *why* a protocol succeeds or fails. This project introduces an **Evidence-Flow Audit** framework that tracks atomic evidence units through the full multi-agent pipeline and diagnoses communication failures at the evidence level.

The audit identifies four failure modes:

| Failure Mode | Definition |
|---|---|
| **Omission** | A critical evidence unit is never transmitted to agents who need it |
| **Distortion** | A critical unit is transmitted but its meaning is altered |
| **Redundancy** | The communication budget is consumed by duplicate units |
| **Aggregation Failure** | Evidence is present on the board but the agent still answers incorrectly |

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
│   ├── run_experiment.py           # Convenience wrapper for Table 1
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

Or copy `.env.example` to `.env` and fill in your key:

```bash
OPENROUTER_API_KEY=your-key-here
```

Use `run.sh` to automatically activate the environment and load `.env`:

```bash
./run.sh python -m src.eval.run_experiment --test
```

---

## Running Experiments

### Table 1 — Protocol comparison

```bash
# Silo-Bench, n=5 agents, all protocols
./run.sh python -m src.eval.run_experiment \
  --benchmark silo_bench \
  --n-agents 5 \
  --protocols all \
  --model deepseek/deepseek-v4-flash \
  --limit 100 \
  --output results/run_silo_n5

# MuSiQue, n=5 agents
./run.sh python -m src.eval.run_experiment \
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
./run.sh python scripts/run_evidence_flow_audit.py \
  --benchmark silo_bench \
  --num-agents 5 \
  --protocols all \
  --model deepseek/deepseek-v4-flash \
  --output-dir outputs/audit_run \
  --limit 50

# Include intervention experiments (deletion curves) and LOO local importance
./run.sh python scripts/run_evidence_flow_audit.py \
  --benchmark musique \
  --num-agents 5 \
  --run-deletions \
  --run-local-importance \
  --model openai/gpt-4.1-mini \
  --output-dir outputs/audit_musique
```

### Compute audit metrics for an existing run

```bash
./run.sh python scripts/compute_audit_metrics.py \
  --run-dir results/run_silo_n5 \
  --summary-exchange
```

### CLI Arguments (run_experiment.py)

| Argument | Default | Description |
|---|---|---|
| `--data` | MuSiQue dev split | Path to JSONL benchmark |
| `--benchmark` | `musique` | `musique` or `silo_bench` |
| `--model` | `deepseek/deepseek-v4-flash` | Model string (OpenRouter format) |
| `--n-agents` | `3` | Agents per instance |
| `--protocols` | `all` | Comma-separated protocol names, or `all` |
| `--max-states` | `3` | Max evidence units extracted per agent |
| `--max-tokens` | `1024` | Per-call output token budget |
| `--max-workers` | `128` | API concurrency |
| `--limit` | `0` (no limit) | Cap on instances |
| `--seed` | `42` | Random seed |
| `--output` | `results/run_<timestamp>/` | Output directory |
| `--test` | `False` | Quick smoke-test: 5 instances |

---

## Supported Models (via OpenRouter)

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

## Output Format

```
results/run_<timestamp>/
├── results.json          # Per-protocol accuracy, token cost, evidence coverage
├── audit_metrics.json    # Omission, distortion, redundancy, aggregation-failure rates
├── local_importance_metrics.json  # LOO importance vs. gold criticality AUC/Spearman
└── summary.txt           # Human-readable table
```

Load results programmatically:

```python
import json

with open("results/run_silo_n5/results.json") as f:
    data = json.load(f)

# Per-protocol metrics
for protocol, metrics in data["protocols"].items():
    print(protocol, metrics["accuracy"], metrics["token_cost"])

# Audit metrics
with open("results/run_silo_n5/audit_metrics.json") as f:
    audit = json.load(f)

print(audit["score_ranked_relay"]["omission_rate"])
print(audit["score_ranked_relay"]["distortion_rate"])
```

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
