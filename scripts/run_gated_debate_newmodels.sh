#!/bin/bash
# Run free_form_debate, confidence_gated, disagreement_gated for the 4 new models
# Results go to separate _gated directories to avoid overwriting existing protocol results.
# Usage: bash scripts/run_gated_debate_newmodels.sh

cd "$(git rev-parse --show-toplevel)"
export $(grep -v '^#' .env | xargs)

PROTOCOLS="free_form_debate,confidence_gated,disagreement_gated"
MAX_WORKERS=32
LOG_DIR="results"
STATUS_FILE="results/gated_debate_status.txt"

log_status() {
    echo "[$(date)] $1" | tee -a $STATUS_FILE
}

run_one() {
    local MODEL=$1
    local SHORT=$2
    local DATASET=$3
    local N_AGENTS=$4
    local MUSIQUE_SAMPLE=$5
    local OUT_DIR=$6
    local LOG_FILE="${OUT_DIR}.log"

    log_status "START $SHORT $DATASET n=$N_AGENTS"
    local CMD="python -m src.eval.run_experiment \
        --model '$MODEL' \
        --dataset $DATASET \
        --protocols $PROTOCOLS \
        --max-workers $MAX_WORKERS \
        --max-tokens 4096 \
        --seed 42 \
        --output $OUT_DIR"
    [ "$N_AGENTS" != "none" ] && CMD="$CMD --n-agents $N_AGENTS"
    [ "$MUSIQUE_SAMPLE" != "0" ]  && CMD="$CMD --musique-sample $MUSIQUE_SAMPLE"

    if eval $CMD > "$LOG_FILE" 2>&1; then
        log_status "DONE $SHORT $DATASET n=$N_AGENTS (exit 0)"
    else
        log_status "FAILED $SHORT $DATASET n=$N_AGENTS (exit $?)"
    fi
}

run_model_serial() {
    local MODEL=$1
    local SHORT=$2
    run_one "$MODEL" "$SHORT" silobench 5    0   "results/run_${SHORT}_n5_gated"
    run_one "$MODEL" "$SHORT" silobench 10   0   "results/run_${SHORT}_n10_gated"
    run_one "$MODEL" "$SHORT" musique   none 100 "results/run_musique_${SHORT}_gated"
    log_status "MODEL DONE: $SHORT"
}

echo "" > $STATUS_FILE
log_status "=== Gated/Debate experiment for 4 new models ==="

# Run all 4 models in parallel (each blocks within itself: n5 -> n10 -> musique)
run_model_serial "google/gemini-2.5-flash-lite"           "geminiflashlite"  &
run_model_serial "openai/gpt-4o-mini"                     "gpt4omini"        &
run_model_serial "deepseek/deepseek-r1-distill-qwen-32b"  "deepseekr1_32b"   &
run_model_serial "google/gemma-4-31b-it"                  "gemma31b"         &

wait
log_status "=== ALL 4 MODELS COMPLETE ==="
