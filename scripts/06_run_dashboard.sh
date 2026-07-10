#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

if [[ -f .env ]]; then
  set -a
  # shellcheck disable=SC1091
  . ./.env
  set +a
fi

EVENTS="${1:-${EVENTS_CSV:-data/input/ssid_events.csv}}"
RESULTS="${2:-${WIGLE_RESULTS_CSV:-data/results/wigle_results.csv}}"

if [[ ! -x .venv/bin/python ]]; then
  echo "[i] Python environment not found. Installing local Python environment now..."
  bash scripts/ensure_venv.sh
fi

if ! .venv/bin/python - <<'PY' >/dev/null 2>&1
import streamlit
PY
then
  echo "[i] Streamlit not found in .venv. Installing requirements now..."
  bash scripts/ensure_venv.sh
fi

mkdir -p "$(dirname "$EVENTS")" "$(dirname "$RESULTS")"
exec .venv/bin/python -m streamlit run app.py -- --events "$EVENTS" --results "$RESULTS"
