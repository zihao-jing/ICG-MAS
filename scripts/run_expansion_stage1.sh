#!/usr/bin/env bash
# Expansion Stage 1: 200 unused MuSiQue dev instances x 3 models, then matcher.
# Approved 2026-11-12; per-pilot cap $5, phase budget $100. Relay calls are
# logged per run in api_responses.jsonl; matcher calls in calls.jsonl.
set -euo pipefail
cd "$(dirname "$0")/.."

DATA=rebuttal/pilots/20261112_expansion_stage1/stage1_instances.jsonl
BASE=rebuttal/results/batch1/expansion_stage1

./run.sh python -m scripts.run_expansion_stage1 --prepare

run_relay () {
  local name="$1" model="$2"
  echo "[stage1] relay $name $model $(date -u +%FT%TZ)"
  ./run.sh python -m src.eval.run_experiment \
    --dataset musique --data "$DATA" \
    --protocols score_ranked_relay --model "$model" \
    --max-tokens 4096 --max-workers 32 --min-hops 2 --seed 42 \
    --output "$BASE/relay_$name"
}

run_relay gemma31b  google/gemma-4-31b-it
run_relay gpt4omini openai/gpt-4o-mini
run_relay qwen235b  qwen/qwen3-235b-a22b-2507

echo "[stage1] matcher $(date -u +%FT%TZ)"
./run.sh python -m scripts.run_expansion_stage1 --match
echo "[stage1] report $(date -u +%FT%TZ)"
./run.sh python -m scripts.run_expansion_stage1 --report
echo "[stage1] done $(date -u +%FT%TZ)"