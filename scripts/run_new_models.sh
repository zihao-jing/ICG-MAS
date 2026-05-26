#!/bin/bash
# Master script for new model robustness experiments (new_exp_plan_24.md)
# Runs 4 new models × 3 datasets = 12 experiment runs + audit metrics
# Models: Gemini-2.5-flash-lite, GPT-4o-mini, DeepSeek-R1-32B, Gemma-4-31B-it

cd "$(git rev-parse --show-toplevel)"

# Load API key
export $(grep -v '^#' .env | xargs)
echo "[$(date)] API key loaded. OPENROUTER_API_KEY starts with: ${OPENROUTER_API_KEY:0:20}..."

PROTOCOLS="single_local,majority_vote,best_local,summary_exchange,random_relay,score_ranked_relay,redundancy_aware_relay,full_sharing"
MAX_WORKERS=64
STATUS_FILE="results/new_models_run_status.txt"

log_status() {
    echo "[$(date)] $1" | tee -a $STATUS_FILE
}

run_experiment() {
    local MODEL=$1
    local DATASET=$2
    local N_AGENTS=$3
    local MUSIQUE_SAMPLE=$4
    local OUT_DIR=$5
    local LOG_FILE="${OUT_DIR}.log"

    log_status "START: model=$MODEL dataset=$DATASET n_agents=$N_AGENTS musique_sample=$MUSIQUE_SAMPLE out=$OUT_DIR"

    local CMD="python -m src.eval.run_experiment \
        --model '$MODEL' \
        --dataset $DATASET \
        --protocols $PROTOCOLS \
        --max-workers $MAX_WORKERS \
        --max-tokens 4096 \
        --seed 42 \
        --output $OUT_DIR"

    if [ "$N_AGENTS" != "none" ]; then
        CMD="$CMD --n-agents $N_AGENTS"
    fi
    if [ "$MUSIQUE_SAMPLE" != "0" ]; then
        CMD="$CMD --musique-sample $MUSIQUE_SAMPLE"
    fi

    if eval $CMD > "$LOG_FILE" 2>&1; then
        log_status "DONE: $OUT_DIR"
    else
        log_status "FAILED: $OUT_DIR (exit code $?)"
        return 1
    fi
}

run_audit() {
    local RUN_DIR=$1
    local LOG_FILE="${RUN_DIR}_audit.log"
    log_status "AUDIT START: $RUN_DIR"
    if python scripts/compute_audit_metrics.py --run-dir "$RUN_DIR" > "$LOG_FILE" 2>&1; then
        log_status "AUDIT DONE: $RUN_DIR/audit_metrics.json"
    else
        log_status "AUDIT FAILED: $RUN_DIR (non-fatal, continuing)"
    fi
}

run_model() {
    local MODEL=$1
    local SHORT=$2
    log_status ""
    log_status "============================================================"
    log_status "MODEL: $MODEL (short=$SHORT)"
    log_status "============================================================"

    run_experiment "$MODEL" "silobench" "5"    "0"   "results/run_${SHORT}_n5"  || true
    run_audit "results/run_${SHORT}_n5" || true

    run_experiment "$MODEL" "silobench" "10"   "0"   "results/run_${SHORT}_n10" || true
    run_audit "results/run_${SHORT}_n10" || true

    run_experiment "$MODEL" "musique"   "none" "100" "results/run_musique_${SHORT}" || true
    run_audit "results/run_musique_${SHORT}" || true

    log_status "MODEL COMPLETE: $MODEL"
}

echo "" > $STATUS_FILE

run_model "google/gemini-2.5-flash-lite"            "geminiflashlite"
run_model "openai/gpt-4o-mini"                      "gpt4omini"
run_model "deepseek/deepseek-r1-distill-qwen-32b"  "deepseekr1_32b"
run_model "google/gemma-4-31b-it"                   "gemma31b"

log_status ""
log_status "============================================================"
log_status "ALL 4 MODELS COMPLETE."
log_status "============================================================"
echo "ALL DONE" >> $STATUS_FILE
