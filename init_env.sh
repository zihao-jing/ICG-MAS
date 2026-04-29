#!/usr/bin/env bash
# =============================================================================
# init_env.sh — Project environment template
# Copy this file, fill in the values for your server, and source it:
#   source init_env.sh
# Do NOT commit server-specific copies to git.
# =============================================================================

# --- Conda environment -------------------------------------------------------
conda activate <ENV_NAME>

# --- Project root -------------------------------------------------------------
export PROJECT_ROOT=<ABSOLUTE_PATH_TO_PROJECT_ROOT>

# --- Data directories ---------------------------------------------------------
export DATA_ROOT=<ABSOLUTE_PATH_TO_DATA_ROOT>
export MUSIQUE_DIR="${DATA_ROOT}/musique"

# --- API keys -----------------------------------------------------------------
export OPENAI_API_KEY=<YOUR_OPENAI_API_KEY>
export ANTHROPIC_API_KEY=<YOUR_ANTHROPIC_API_KEY>
export GEMINI_API_KEY=<YOUR_GEMINI_API_KEY>
export OPENROUTER_API_KEY=<YOUR_OPENROUTER_API_KEY>

# --- OpenRouter optional attribution (shown on openrouter.ai leaderboard) ----
export OPENROUTER_HTTP_REFERER=<YOUR_SITE_URL>      # e.g. https://yourproject.com
export OPENROUTER_APP_TITLE=<YOUR_APP_NAME>          # e.g. ICG-MAS

echo "Environment initialised."
