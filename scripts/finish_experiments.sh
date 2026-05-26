#!/bin/bash
# Waits for remaining experiment runs to complete, re-audits each with --summary-exchange,
# then compiles the final LaTeX appendix.

cd "$(git rev-parse --show-toplevel)"
export $(grep -v '^#' .env | xargs)

LOG="results/finish_experiments.log"
date >> $LOG
echo "=== finish_experiments.sh started ===" >> $LOG

wait_and_audit() {
    local DIR="$1"
    local LABEL="$2"
    echo "[$(date)] Waiting for $LABEL..." | tee -a $LOG
    until [ -f "$DIR/results.json" ]; do sleep 60; done
    echo "[$(date)] $LABEL complete. Re-auditing..." | tee -a $LOG
    python scripts/compute_audit_metrics.py --run-dir "$DIR" --summary-exchange >> "${DIR}_reaudit.log" 2>&1
    echo "[$(date)] $LABEL re-audit done." | tee -a $LOG
}

# DeepSeek n10 (master script started it at 23:53)
wait_and_audit "results/run_deepseekr1_32b_n10" "DeepSeek-R1-32B n10"

# DeepSeek MuSiQue
wait_and_audit "results/run_musique_deepseekr1_32b" "DeepSeek-R1-32B MuSiQue"

# Gemma n5
wait_and_audit "results/run_gemma31b_n5" "Gemma-4-31B n5"

# Gemma n10
wait_and_audit "results/run_gemma31b_n10" "Gemma-4-31B n10"

# Gemma MuSiQue
wait_and_audit "results/run_musique_gemma31b" "Gemma-4-31B MuSiQue"

echo "[$(date)] All remaining runs complete. Compiling final LaTeX..." | tee -a $LOG

# Generate final LaTeX
python scripts/compile_new_model_results.py 2>&1 | tee -a $LOG

echo "[$(date)] LaTeX tables generated." | tee -a $LOG

echo "[$(date)] === finish_experiments.sh COMPLETE ===" | tee -a $LOG
