#!/usr/bin/env bash
# Run SILO-BENCH experiments.
#
# Prerequisites:
#   1. Copy configs/config.example.yaml to configs/config.yaml
#   2. Fill in your API credentials in configs/config.yaml
#
# Usage:
#   ./run.sh                                    # Run all tasks with default profile
#   ./run.sh --profile grok                     # Use grok profile from config.yaml
#   ./run.sh --levels I --agent-counts 2        # Only Level I, 2-agent cases
#   ./run.sh --protocols msg --workers 4        # Only P2P protocol, 4 workers
#
# All arguments are forwarded to batch_run.py.

set -euo pipefail

uv run python -m src.batch_run \
    --task-dir benchmarks \
    --protocols msg broadcast sfs \
    --max-rounds 100 \
    --workspace workspace \
    --workers 1 \
    "$@"
