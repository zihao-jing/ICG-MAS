#!/bin/bash
# Run distortion+SE audit on all run directories that have Summary Exchange data.
# Results saved to audit_metrics.json in each run directory.
set -euo pipefail

cd "$(git rev-parse --show-toplevel)"
export $(grep -v '^#' .env | xargs)

LOG="results/distortion_audits.log"
echo "$(date) === run_distortion_audits.sh started ===" | tee "$LOG"

run_dist() {
    local DIR="$1"
    echo "$(date '+%H:%M:%S') START: $DIR" | tee -a "$LOG"
    python scripts/compute_audit_metrics.py \
        --run-dir "results/$DIR" \
        --summary-exchange \
        --distortion \
        --max-workers 32 \
        >> "results/${DIR}_distaudit.log" 2>&1 \
        && echo "$(date '+%H:%M:%S') DONE:  $DIR" | tee -a "$LOG" \
        || echo "$(date '+%H:%M:%S') FAIL:  $DIR (exit $?)" | tee -a "$LOG"
}

# Main paper models — Silo-Bench
run_dist run_qwen235b_n5
run_dist run_qwen235b_n10
run_dist run_mistrals
run_dist run_mistrals_n10
run_dist run_qwen80bt
run_dist run_qwen80bt_n10
run_dist run_20260523_214416     # Qwen-3.6-Flash n5
run_dist run_silobench_n10       # Qwen-3.6-Flash n10
run_dist run_ring1t_n10
run_dist run_gptoss_n10
run_dist run_gptoss_v2

# Main paper models — MuSiQue
run_dist run_qwen235b_musique
run_dist run_musique_mistrals
run_dist run_musique_qwen80bt
run_dist run_musique_100         # Qwen-3.6-Flash MuSiQue
run_dist run_musique_ring1t
run_dist run_musique_gptoss

# New models — Silo-Bench
run_dist run_geminiflashlite_n5
run_dist run_geminiflashlite_n10
run_dist run_gpt4omini_n5
run_dist run_gpt4omini_n10
run_dist run_deepseekr1_32b_n5
run_dist run_deepseekr1_32b_n10
run_dist run_gemma31b_n5
run_dist run_gemma31b_n10

# New models — MuSiQue
run_dist run_musique_geminiflashlite
run_dist run_musique_gpt4omini
run_dist run_musique_deepseekr1_32b
run_dist run_musique_gemma31b

echo "$(date) === All distortion audits complete ===" | tee -a "$LOG"

# Regenerate all LaTeX tables
echo "$(date '+%H:%M:%S') Compiling LaTeX tables..." | tee -a "$LOG"
python scripts/compile_new_model_results.py >> "$LOG" 2>&1 \
    && echo "$(date '+%H:%M:%S') compile_new_model_results.py done" | tee -a "$LOG" \
    || echo "$(date '+%H:%M:%S') compile_new_model_results.py FAILED" | tee -a "$LOG"

python scripts/compile_multimodel_audit.py >> "$LOG" 2>&1 \
    && echo "$(date '+%H:%M:%S') compile_multimodel_audit.py done" | tee -a "$LOG" \
    || echo "$(date '+%H:%M:%S') compile_multimodel_audit.py FAILED (script may not exist yet)" | tee -a "$LOG"

echo "$(date) === run_distortion_audits.sh COMPLETE ===" | tee -a "$LOG"
