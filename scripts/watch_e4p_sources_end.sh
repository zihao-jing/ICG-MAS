#!/usr/bin/env bash
# Waits for all three E4-P source-trace processes to exit, then prints the per-model report (their own, unsealed logs).
for PID in "$@"; do while kill -0 "$PID" 2>/dev/null; do sleep 60; done; done
echo "all E4-P source-trace PIDs exited at $(date -u +%FT%TZ)"
cd "$(dirname "$0")/.."
./run.sh python -m scripts.report_e4p_sources
for m in qwen gpt gemma; do echo "== $m last log line: $(tail -1 rebuttal/results/batch1/E4P_seed43/$m/run.log)"; done
