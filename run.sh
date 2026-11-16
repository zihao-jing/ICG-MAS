#!/usr/bin/env bash
# run.sh — Run a command using the local environment, active Python, or the ef-audit conda environment.
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

LOCAL_PYTHON="$SCRIPT_DIR/.conda-env/bin/python"
if [[ -x "$LOCAL_PYTHON" ]]; then
    # Preserve the documented `./run.sh python ...` interface while using the
    # repository-local environment created for this project.
    if [[ "${1:-}" == "python" ]]; then
        shift
        exec "$LOCAL_PYTHON" "$@"
    fi
    export PATH="$SCRIPT_DIR/.conda-env/bin:$PATH"
    exec "$@"
fi

if [[ -n "${CONDA_PREFIX:-}${VIRTUAL_ENV:-}" ]]; then
    exec "$@"
fi

exec conda run --no-capture-output -n ef-audit "$@"
