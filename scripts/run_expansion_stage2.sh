#!/usr/bin/env bash
# Expansion Stage 2: 800 unused MuSiQue dev instances x 3 models, then matcher.
# Approved 2026-11-12; cap $5. Relay calls are logged per run in
# api_responses.jsonl; matcher calls in each shard's calls.jsonl.
set -euo pipefail
cd "$(dirname "$0")/.."

DATA=rebuttal/pilots/20261112_expansion_stage2/stage2_instances.jsonl
BASE=rebuttal/results/batch1/expansion_stage2

./run.sh python -m scripts.run_expansion_stage2 --prepare

run_relay () {
  local name="$1" model="$2"
  echo "[stage2] relay $name $model $(date -u +%FT%TZ)"
  ./run.sh python -m src.eval.run_experiment \
    --dataset musique --data "$DATA" \
    --protocols score_ranked_relay --model "$model" \
    --max-tokens 4096 --max-workers 32 --min-hops 2 --seed 42 \
    --output "$BASE/relay_$name"
}

run_relay gemma31b  google/gemma-4-31b-it
run_relay gpt4omini openai/gpt-4o-mini
run_relay qwen235b  qwen/qwen3-235b-a22b-2507

echo "[stage2] matcher $(date -u +%FT%TZ)"
./run.sh python -m scripts.run_expansion_stage2 --match
echo "[stage2] report $(date -u +%FT%TZ)"
./run.sh python -m scripts.run_expansion_stage2 --report
echo "[stage2] done $(date -u +%FT%TZ)"