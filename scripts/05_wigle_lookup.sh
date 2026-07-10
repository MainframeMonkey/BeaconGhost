#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

if [[ -f .env ]]; then
  set -a
  # shellcheck disable=SC1091
  . ./.env
  set +a
fi

IN="${1:-${EVENTS_CSV:-data/input/ssid_events.csv}}"
OUT="${2:-${WIGLE_RESULTS_CSV:-data/results/wigle_results.csv}}"
CACHE="${WIGLE_CACHE:-data/cache/wigle_cache.json}"
FRAME_TYPE="${WIGLE_FRAME_TYPE:-probe_request}"

PYTHON_BIN="${PYTHON:-}"
if [[ -z "$PYTHON_BIN" ]]; then
  if [[ ! -x .venv/bin/python ]]; then
    echo "[i] Python virtual environment not found. Installing local dependencies now..."
    bash scripts/ensure_venv.sh
  fi
  PYTHON_BIN=".venv/bin/python"
fi

"$PYTHON_BIN" -m beaconghost.wigle_client \
  --input "$IN" \
  --output "$OUT" \
  --cache "$CACHE" \
  --frame-type "$FRAME_TYPE" \
  --max-results "${WIGLE_MAX_RESULTS_PER_SSID:-10}" \
  --sleep "${WIGLE_SLEEP_SECONDS:-2.0}" \
  --coord-precision "${WIGLE_COORD_PRECISION:-3}" \
  --mode "${WIGLE_LOOKUP_MODE:-exact}" \
  --max-new-lookups "${WIGLE_MAX_NEW_LOOKUPS_PER_RUN:-10}"
