#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
EVENTS="${1:-${EVENTS_CSV:-data/input/ssid_events.csv}}"
RESULTS="${2:-${WIGLE_RESULTS_CSV:-data/results/wigle_results.csv}}"
bash scripts/06_run_dashboard.sh "$EVENTS" "$RESULTS"
