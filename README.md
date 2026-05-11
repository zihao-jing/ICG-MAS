# ICG-MAS

**Measuring the Irreducible Communication Gap in Multi-Agent LLM Systems**

Experimental codebase for the paper *"Measuring the Irreducible Communication Gap in Multi-Agent LLM Systems"* (Zihao Jing et al., targeting ICLR/AAAI 2027).

---

## Overview

Multi-agent LLM systems are increasingly framed as a form of test-time scaling, but communication gains vary widely across tasks and stronger no-communication baselines sometimes match or exceed communication protocols. The root issue is that existing evaluations conflate two distinct questions:

- **Communication necessity** — Is communication required by the task structure?
- **Protocol effectiveness** — Does this specific protocol help?

This project introduces the **Irreducible Communication Gap (ICG)**, a principled, task-side metric that measures when communication between agents is *structurally necessary* — independent of model capability, communication protocol, or token budget.

---

## The ICG Metric

```
ICG(x) = |S*(x)| - max_i |S*(x) ∩ U_i|
```

- `S*(x)` — minimum-cardinality evidence set sufficient to correctly answer question `x`
- `U_i` — evidence units accessible to agent `i`
- `max_i |S*(x) ∩ U_i|` — how much the most-informed single agent overlaps with the minimal support

| ICG | Interpretation |
|-----|----------------|
| 0   | Some agent alone holds all minimally required evidence → communication not structurally necessary |
| > 0 | At least `k` evidence units in the minimal support lie outside any single agent's view → communication structurally necessary |

Key properties: task-side only (independent of model/protocol), conservative (ICG=0 means unnecessary, not harmful), and quantitative (higher ICG = more distributed evidence = more communication needed).

---

## Research Hypotheses

| Hypothesis | Statement |
|------------|-----------|
| **H1** | ICG is higher on benchmarks with genuinely distributed evidence (Silo-Bench, Sharded MuSiQue) than on hard-but-non-distributed tasks (GPQA) |
| **H2** | Communication gains `Δ = F1_centralized − F1_isolated` correlate positively with ICG |
| **H3** | ICG responds predictably to evidence properties: dispersion↑ → ICG↑, redundancy↑ → ICG↓, asymmetry↑ → ICG↓ |

---

## Benchmarks

| Benchmark | Type | ICG Profile | Role |
|-----------|------|-------------|------|
| **Sharded MuSiQue** | Multi-hop QA (2–4 hops) | Controlled, varies with hop count and sharding strategy | Primary evaluation |
| **Silo-Bench** | Hidden-profile tasks | High ICG by construction | Tests metric validity |
| **GPQA-Diamond** | Expert science QA | Low ICG (hard but not distributed) | Control condition |

---

## Directory Structure

```
ICG-MAS/
├── src/
│   ├── eval/
│   │   ├── data_loader.py        # MuSiQue loading + ICG computation
│   │   ├── silo_bench_loader.py  # Silo-Bench loading
│   │   ├── variant_a.py          # Distributed isolated-agent evaluation (Condition A)
│   │   ├── variant_b.py          # Centralized single-agent baseline (Condition B)
│   │   ├── evaluate.py           # F1, majority vote, correlation metrics
│   │   ├── metrics.py            # Recovery and secondary metrics
│   │   ├── compute_metrics.py    # Post-hoc ROUGE/BLEU/BERTScore
│   │   ├── ablation_study.py     # Table 2: protocol ablations
│   │   ├── bottleneck_analysis.py# Table 3: critical evidence bottleneck analysis
│   │   └── run_experiment.py     # CLI entry point
│   └── protocols/
│       ├── base.py               # Shared types: AgentShard, ProtocolResult
│       ├── local.py              # Local-only (no communication) baseline
│       ├── full_sharing.py       # Full evidence sharing protocol
│       ├── relay.py              # CSC relay protocols (random, top-k, redundancy)
│       ├── summary_exchange.py   # Summary-exchange protocol
│       ├── gated.py              # Gated communication protocol
│       └── debate.py             # Debate protocol
├── utility/apis/
│   ├── base.py                   # Unified APIRequest / APIResponse types
│   ├── openrouter_api.py         # Primary interface (200+ models via OpenRouter)
│   ├── claude_api.py             # Anthropic direct adapter
│   ├── openai_api.py             # OpenAI direct adapter
│   └── gemini_api.py             # Google Gemini adapter
├── tests/
│   └── test_eval.py              # 70+ unit tests (all mock-based, no API keys needed)
├── data/                         # Not in git — local datasets
│   ├── musique/
│   │   └── musique_ans_v1.0_dev.jsonl
│   └── silo-bench/
│       └── benchmarks/
├── results/                      # Not in git — experiment outputs
├── run.sh                        # Convenience wrapper (activates icg-mas conda env)
└── requirements.txt
```

---

## Setup

```bash
# Create and activate the conda environment
conda create -n icg-mas python=3.11
conda activate icg-mas
pip install -r requirements.txt

# Set API key (OpenRouter is the primary interface)
export OPENROUTER_API_KEY="your-key-here"
```

Place datasets at:
- `data/musique/musique_ans_v1.0_dev.jsonl` (MuSiQue dev split)
- `data/silo-bench/benchmarks/` (Silo-Bench JSON files)

---

## Running Experiments

Use `run.sh` to automatically activate the `icg-mas` conda env and load `.env`:

```bash
# A1 sharding, 100 instances, DeepSeek-V4-Flash via OpenRouter
./run.sh python -m src.eval.run_experiment \
  --data data/musique/musique_ans_v1.0_dev.jsonl \
  --model deepseek/deepseek-v4-flash \
  --setting a1 \
  --limit 100 \
  --output results/deepseek_a1_n100

# Run all three sharding strategies
./run.sh python -m src.eval.run_experiment \
  --data data/musique/musique_ans_v1.0_dev.jsonl \
  --model openai/gpt-4.1-mini \
  --setting all \
  --limit 200 \
  --output results/gpt4mini_all_n200

# Isolated-only run (no Variant B, faster)
./run.sh python -m src.eval.run_experiment \
  --data data/musique/musique_ans_v1.0_dev.jsonl \
  --model openai/gpt-4.1-mini \
  --setting a1 \
  --skip-b \
  --limit 100 \
  --output results/gpt4mini_a1_isolated_only

# Protocol ablation study (Table 2)
./run.sh python -m src.eval.ablation_study

# Bottleneck analysis (Table 3)
./run.sh python -m src.eval.bottleneck_analysis
```

### CLI Arguments

| Argument | Default | Description |
|----------|---------|-------------|
| `--data` | required | Path to MuSiQue JSONL file |
| `--model` | required | Model string in OpenRouter format (`"provider/model"`) |
| `--setting` | `a1` | Sharding strategy: `a1`, `a2`, `a3`, or `all` |
| `--max-tokens` | 512 | Token budget per agent (same for Condition A and B) |
| `--max-workers` | 2 | Concurrent API calls |
| `--limit` | None | Max instances (for quick tests) |
| `--seed` | 42 | Random seed |
| `--skip-b` | False | Skip centralized baseline |
| `--output` | required | Output directory |

### Supported Models (via OpenRouter)

```python
# OpenAI
"openai/gpt-4.1-mini"
"openai/gpt-4.1"
"openai/o3-mini"

# Anthropic
"anthropic/claude-3.5-haiku"
"anthropic/claude-sonnet-4-6"

# Google
"google/gemini-2.0-flash-001"
"google/gemini-2.5-pro"

# DeepSeek
"deepseek/deepseek-v4-flash"
```

---

## Communication Protocols

The `src/protocols/` module implements the communication protocols compared in the paper:

| Protocol | Description |
|----------|-------------|
| `local` | No communication — each agent answers from its private shard only |
| `full_sharing` | All agents share their full evidence with each other |
| `relay` (CSC) | Composite Necessity Scoring: agents extract atomic states, score by relevance × uniqueness × criticality, relay top-k or apply redundancy penalty |
| `summary_exchange` | Agents send natural-language summaries instead of atomic states |
| `gated` | Communication only when necessity score exceeds a threshold |
| `debate` | Iterative answer-exchange and revision |

The **CSC relay** protocol (Section 3 of the paper) is the primary contribution: it scores each atomic fact by a composite necessity score and selects which facts to relay across agents, directly operationalizing the ICG metric.

---

## Experimental Design

**Condition A — Isolated (Distributed)**
- Each agent receives only its private evidence shard (A1: 1 paragraph/agent, A2: 2 paragraphs/agent, A3: 3 paragraphs/agent)
- Strict grounding: agents answer only from their shard
- Reports: oracle best-agent F1, majority-vote F1

**Condition B — Centralized (Baseline)**
- Single agent receives all supporting paragraphs
- Same token budget as individual agents in Condition A
- Reports: centralized F1 (upper bound for communication benefit)

**Key metric**: `Δ = F1_B − F1_A`. A positive `correlation(ICG, Δ)` validates H2.

---

## Outputs

```
results/run1/
├── results.json          # Full structured results (instance-level + aggregated)
├── summary.txt           # Human-readable per-stratum stats and correlations
└── detail_<setting>.txt  # Per-instance logs
```

Example `summary.txt`:
```
Setting: A1
ICG  |  N  | F1_A  | F1_B  | Delta
  1  |  80 | 0.123 | 0.441 | 0.318
  2  |  45 | 0.087 | 0.502 | 0.415
  3  |  20 | 0.041 | 0.531 | 0.490

Correlation(ICG, Delta):  Pearson=0.71 (p=0.002), Spearman=0.68 (p=0.004)
Filtered correlation:     Pearson=0.74 (p=0.001), Spearman=0.71 (p=0.003)
```

Load results programmatically:
```python
import json
with open("results/run1/results.json") as f:
    data = json.load(f)

data["settings"]["a1"]["aggregated"]          # per-stratum stats
data["settings"]["a1"]["instance_results"]    # instance-level results
data["settings"]["a1"]["correlation"]         # full-dataset correlation
data["settings"]["a1"]["filtered_correlation"]# excluding self-sufficient instances
```

### Secondary Metrics

After a full run, compute ROUGE, BLEU, and BERTScore:
```bash
./run.sh python -m src.eval.compute_metrics \
  --results results/run1/results.json \
  --output results/run1
```

---

## Tests

```bash
# All tests — no API keys required (fully mocked)
./run.sh python -m pytest tests/test_eval.py -v

# Specific test class
./run.sh python -m pytest tests/test_eval.py::TestVariantA -v
```

---

## Common Issues

| Issue | Fix |
|-------|-----|
| `OPENROUTER_API_KEY` not set | Export the env var or add to `.env` at repo root |
| MuSiQue file not found | Download the official MuSiQue dev split and place at `data/musique/musique_ans_v1.0_dev.jsonl` |
| Rate limiting errors | Reduce `--max-workers` to 1 |
| Weak ICG correlation | Increase `--limit` or use `--setting all` for more ICG strata |
