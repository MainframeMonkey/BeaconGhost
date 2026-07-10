#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

if [[ ! -x .venv/bin/python ]] || ! .venv/bin/python -c "import streamlit" >/dev/null 2>&1; then
  echo "[i] Python environment missing. Installing automatically..."
  bash scripts/00_install_kali.sh
fi

EVENTS="${1:-data/input/ssid_events.csv}"
RESULTS="${2:-data/results/wigle_results.csv}"
bash scripts/06_run_dashboard.sh "$EVENTS" "$RESULTS"
