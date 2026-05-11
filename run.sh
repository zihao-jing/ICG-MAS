#!/usr/bin/env bash
# run.sh — Run any command in the icg-mas conda environment.
#
# Usage examples:
#   ./run.sh python -m src.eval.run_experiment --test
#   ./run.sh python -m src.eval.run_experiment --model deepseek/deepseek-v4-flash --limit 100
#   ./run.sh python -m pytest tests/ -v

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [[ -f "$SCRIPT_DIR/.env" ]]; then
    set -a
    # shellcheck source=/dev/null
    source "$SCRIPT_DIR/.env"
    set +a
fi

exec conda run --no-capture-output -n icg-mas "$@"
