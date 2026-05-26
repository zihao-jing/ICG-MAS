#!/bin/bash
# Re-run audit with --summary-exchange for all new model runs
cd "$(git rev-parse --show-toplevel)"
export $(grep -v '^#' .env | xargs)

DIRS=(
    "run_geminiflashlite_n5"
    "run_geminiflashlite_n10"
    "run_musique_geminiflashlite"
    "run_gpt4omini_n5"
    "run_gpt4omini_n10"
    "run_musique_gpt4omini"
    "run_deepseekr1_32b_n5"
    "run_deepseekr1_32b_n10"
    "run_musique_deepseekr1_32b"
    "run_gemma31b_n5"
    "run_gemma31b_n10"
    "run_musique_gemma31b"
)

for DIR in "${DIRS[@]}"; do
    FULL="results/$DIR"
    if [ -f "$FULL/results.json" ]; then
        echo "[$(date)] Re-auditing $DIR with --summary-exchange..."
        python scripts/compute_audit_metrics.py --run-dir "$FULL" --summary-exchange \
            > "${FULL}_reaudit.log" 2>&1
        echo "[$(date)] Done: $DIR"
    else
        echo "[$(date)] SKIP: $DIR (no results.json yet)"
    fi
done

echo "[$(date)] All re-audits complete."
