#!/usr/bin/env bash
# Regenerates STATUS.md every 4 minutes while any tracked job runs, then once more after the last one exits.
cd "$(dirname "$0")/.."
running(){ pgrep -f "scripts\.(run_|pilot_)[a-z0-9_]+" >/dev/null; }   # same pattern as scripts/status_supervisor.py
while true; do
  ./run.sh python -m scripts.make_status >/dev/null 2>&1
  if ! running; then sleep 20; ./run.sh python -m scripts.make_status >/dev/null 2>&1; break; fi
  sleep 240
done
echo "status loop finished at $(date -u +%FT%TZ)"
