#!/usr/bin/env bash
# Rebuild the completed three-model crossover report from immutable run directories.
set -euo pipefail
cd "$(dirname "$0")/.."
root=iclr2027_paper/experiments/repair/results
PYTHONPATH=. .conda-env/bin/python -m scripts.summarize_frozen_repair_matrix \
  --runs \
  "$root/gemma31b_musique_full" \
  "$root/gemma31b_silobench_n5_full" \
  "$root/gemma31b_silobench_n10_network" \
  "$root/gemma31b_silobench_n10_supplement" \
  "$root/gpt4omini_musique_full" \
  "$root/gpt4omini_silobench_n5_full" \
  "$root/gpt4omini_silobench_n10_full" \
  "$root/qwen235b_musique_full" \
  "$root/qwen235b_silobench_n5_full" \
  "$root/qwen235b_silobench_n10_full" \
  "$root/gemma31b_musique_cross" \
  "$root/gemma31b_silobench_n5_cross" \
  "$root/gemma31b_silobench_n10_cross" \
  "$root/gpt4omini_musique_cross" \
  "$root/gpt4omini_silobench_n5_cross" \
  "$root/gpt4omini_silobench_n10_cross" \
  "$root/qwen235b_musique_cross" \
  "$root/qwen235b_silobench_n5_cross" \
  "$root/qwen235b_silobench_n10_cross" \
  --output "$root/three_model_summary" --overwrite
