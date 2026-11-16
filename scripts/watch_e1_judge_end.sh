#!/usr/bin/env bash
# Waits for an E1 judge process to exit, then prints the counts-only end-of-run report. Opens no ledger and no sealed file.
# Usage: watch_e1_judge_end.sh PID [summary.json] [counts-only log]
PID=${1:-50439}; SUMMARY=${2:-rebuttal/results/batch1/E1_judge_retry_summary.json}; LOG=${3:-rebuttal/results/batch1/E1_judge_retry.log}
while kill -0 "$PID" 2>/dev/null; do sleep 60; done
echo "PID $PID exited at $(date -u +%FT%TZ)"
cd "$(dirname "$0")/.."
./run.sh python -m scripts.report_sealed_run_end "$SUMMARY"
echo "--- how far the log got (counts only):"
./run.sh python -m scripts.status_counts_only "$LOG"
echo "--- last log lines:"; tail -3 "$LOG"
