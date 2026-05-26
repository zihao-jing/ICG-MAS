# SILO-Bench Benchmark Generator

> 📌 **[← Back to Main README](../README.md)**

This directory contains the benchmark generator for SILO-Bench, a multi-agent system benchmark for evaluating distributed coordination in LLM-based multi-agent systems.

## Overview

The benchmark generator creates JSON task files that can be directly used by the SILO-Bench execution engine. It generates **30 unique tasks** across three paradigms:

| Paradigm | Tasks | Description | Complexity |
|----------|-------|-------------|------------|
| **I** (MapReduce/Aggregation) | I-01 to I-10 | Independent local processing + simple aggregation | O(N) |
| **II** (Structured Mesh/Stencil) | II-11 to II-20 | Spatial locality, boundary exchange with neighbors | O(N) |
| **III** (Unstructured/Global) | III-21 to III-30 | Complex dependencies, global communication | O(N log N) to O(N²) |

## Quick Start

```bash
# Generate benchmarks for all agent counts (2, 5, 10, 20, 50, 100)
python main.py

# Generate benchmarks for specific agent counts
python main.py --agent-counts 2 5 10

# Generate to a custom directory
python main.py --agent-counts 2 5 --output-dir ./my_benchmarks
```

## Usage

### Command Line Arguments

| Argument | Short | Default | Description |
|----------|-------|---------|-------------|
| `--agent-counts` | `-c` | `2 5 10 20 50 100` | List of agent counts to generate benchmarks for |
| `--output-dir` | `-o` | `../benchmarks` | Output directory for benchmark files |
| `--num-agents` | `-n` | (deprecated) | Use `--agent-counts` instead |

### Examples

```bash
# Generate all 180 benchmark files (30 tasks × 6 agent counts)
python main.py

# Generate only small-scale benchmarks for testing
python main.py --agent-counts 2 5

# Generate benchmarks and output to project root benchmarks directory
python main.py --output-dir ../benchmarks
```

## Output Format

### File Naming Convention

Generated files follow the pattern: `{TASK_ID}_n{AGENT_COUNT}.json`

Examples:
- `I-01_n2.json` - Global Max task with 2 agents
- `II-11_n10.json` - Prefix Sum task with 10 agents
- `III-21_n100.json` - Distributed Sort task with 100 agents

### JSON Structure

Each benchmark file contains:

```json
{
  "case_id": "I-01",
  "case_name": "Global Max",
  "paradigm": "Paradigm I",
  "metadata": {
    "num_agents": 2,
    "optimal_topology": "Star (all agents → leader) or Tree",
    "optimal_message_count": "...",
    "theoretical_complexity": "O(N) - MapReduce/Aggregation",
    "is_segmented": false
  },
  "task_description": "...",
  "agent_configs": [
    {
      "agent_id": 0,
      "system_prompt": "...",
      "user_prompt": "...",
      "input_shard": [...],
      "expected_output": 990
    },
    {
      "agent_id": 1,
      "system_prompt": "...",
      "user_prompt": "...",
      "input_shard": [...],
      "expected_output": 990
    }
  ],
  "expected_output": {
    "type": "distributed",
    "per_agent_values": [990, 990],
    "is_segmented": false,
    "verification_logic": "..."
  }
}
```

### Key Fields

| Field | Description |
|-------|-------------|
| `agent_configs[].agent_id` | Unique identifier for each agent (0 to N-1) |
| `agent_configs[].system_prompt` | Base system prompt (overridden at runtime by protocol-specific prompt) |
| `agent_configs[].user_prompt` | Task-specific prompt with agent's data |
| `agent_configs[].input_shard` | Agent's portion of the input data |
| `agent_configs[].expected_output` | Expected answer this agent should submit |
| `expected_output.is_segmented` | If `true`, each agent submits different output; if `false`, all submit same answer |

## Integration with Execution Engine

The generated benchmarks are directly compatible with the SILO-Bench execution engine:

```bash
# 1. Generate benchmarks
cd benchmark_generator
python main.py --agent-counts 2 5 --output-dir ../benchmarks

# 2. Run experiments
cd ..
./run.sh --task-dir benchmarks --levels I --agent-counts 2 --protocols msg
```

### Important Notes

1. **System Prompt Override**: The `system_prompt` field in benchmark files is a **placeholder**. At runtime, the execution engine (`src/engine.py`) generates protocol-specific system prompts based on the chosen protocol (msg/broadcast/sfs). The placeholder text clearly indicates this:
   ```
   [PLACEHOLDER] This system_prompt will be overridden at runtime by protocol-specific prompts.
   ```

2. **Protocol-Specific Tools**:
   - **msg** (P2P): `send_message`, `receive_messages`, `wait`, `submit_result`
   - **broadcast**: `broadcast_message`, `receive_messages`, `list_agents`, `wait`, `submit_result`
   - **sfs** (Shared File System): `list_files`, `read_file`, `write_file`, `delete_file`, `wait`, `submit_result`

3. **Verification**: The `verification_logic` field is for documentation purposes. Actual evaluation uses direct value comparison in `src/utils/metrics.py`.

## Task Descriptions

### Paradigm I: MapReduce/Aggregation (I-01 to I-10)

Tasks with embarrassingly parallel computations and simple aggregation:

| Task | Name | Description |
|------|------|-------------|
| I-01 | Global Max | Find maximum value across all data |
| I-02 | Word Frequency | Count occurrences of target word |
| I-03 | Distributed Vote | Find candidate with most votes |
| I-04 | Any Match | Check if any string contains "ERROR" |
| I-05 | Range Count | Count numbers in range [L, R] |
| I-06 | Checksum | Compute XOR checksum |
| I-07 | Average Value | Compute global average |
| I-08 | Set Union Size | Count distinct elements |
| I-09 | Top-K Select | Find K largest elements |
| I-10 | Standard Deviation | Two-phase std dev computation |

### Paradigm II: Structured Mesh/Stencil (II-11 to II-20)

Tasks with spatial locality requiring neighbor communication:

| Task | Name | Description |
|------|------|-------------|
| II-11 | Prefix Sum | Cumulative sum (segmented output) |
| II-12 | Moving Average | Window=3 moving average |
| II-13 | Longest Palindrome | Cross-boundary palindrome detection |
| II-14 | 1D Life Game | Cellular automaton simulation (segmented) |
| II-15 | Pattern Search | State machine across boundaries |
| II-16 | Trapping Rain | Bidirectional height propagation |
| II-17 | Diff Array | Compute differences |
| II-18 | List Ranking | Distributed linked list ranking |
| II-19 | Merge Neighbors | Boundary deduplication |
| II-20 | Pipeline Hash | Blockchain-style sequential hash (segmented) |

### Paradigm III: Unstructured/Global (III-21 to III-30)

Tasks requiring global communication and data shuffling:

| Task | Name | Description |
|------|------|-------------|
| III-21 | Distributed Sort | Global data redistribution (segmented) |
| III-22 | Median of Medians | Iterative convergence to median |
| III-23 | Graph Components | Distributed union-find |
| III-24 | BFS Distance | Multi-hop message propagation |
| III-25 | K-Means Iteration | Clustering coordination |
| III-26 | Global Distinct | Hash-based deduplication |
| III-27 | Collaborative Filtering | All-pairs scoring |
| III-28 | PageRank Step | Graph value propagation |
| III-29 | Load Balance | Deterministic greedy redistribution |
| III-30 | Matrix Multiply | Distributed linear algebra |

## File Structure

```
benchmark_generator/
├── main.py           # Main entry point and BenchmarkGenerator class
├── paradigm_i.py     # Paradigm I task generators (I-01 to I-10)
├── paradigm_ii.py    # Paradigm II task generators (II-11 to II-20)
├── paradigm_iii.py   # Paradigm III task generators (III-21 to III-30)
└── README.md         # This file
```

## Reproducibility

The generator uses `random.seed(42)` in each paradigm file to ensure reproducible benchmark generation. Running the generator multiple times with the same parameters will produce identical output.

## License

This project is part of SILO-Bench. See the [main LICENSE](../LICENSE) file.
