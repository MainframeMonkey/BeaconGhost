#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."
EVENTS="${1:-${EVENTS_CSV:-data/input/ssid_events.csv}}"
RESULTS="${2:-${WIGLE_RESULTS_CSV:-data/results/wigle_results.csv}}"
OUT="${3:-data/results/showcase_report.md}"

PYTHON_BIN="${PYTHON:-}"
if [[ -z "$PYTHON_BIN" ]]; then
  if [[ ! -x .venv/bin/python ]]; then
    echo "[i] Python virtual environment not found. Installing local dependencies now..."
    bash scripts/ensure_venv.sh
  fi
  PYTHON_BIN=".venv/bin/python"
fi

"$PYTHON_BIN" - <<PY
from beaconghost.reporting import export_markdown
export_markdown('$EVENTS', '$RESULTS', '$OUT')
print('Wrote $OUT')
PY
