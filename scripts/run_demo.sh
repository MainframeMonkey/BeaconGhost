#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

if [[ -f .env ]]; then
  set -a
  # shellcheck disable=SC1091
  . ./.env
  set +a
fi

if [[ ! -x .venv/bin/python ]]; then
  echo "[i] Python virtual environment not found. Installing local dependencies now..."
  bash scripts/ensure_venv.sh
fi

IFACE="${1:-${WIFI_INTERFACE:-}}"
DURATION="${2:-${CAPTURE_DURATION:-60}}"
CHANNEL="${3:-${WIFI_CHANNEL:-}}"
EVENTS="${EVENTS_CSV:-data/input/ssid_events.csv}"
RESULTS="${WIGLE_RESULTS_CSV:-data/results/wigle_results.csv}"

if [[ -z "$IFACE" ]]; then
  echo "Usage: bash scripts/run_demo.sh <wireless_interface> [duration_seconds] [channel]" >&2
  exit 1
fi

bash scripts/01_preflight.sh "$IFACE"
MON_IFACE="$(sudo -E bash scripts/02_start_monitor.sh "$IFACE" "$CHANNEL" | tail -n 1)"
cleanup() {
  sudo -E bash scripts/04_stop_monitor.sh "$MON_IFACE" || true
}
trap cleanup EXIT

bash scripts/03_capture_ssids.sh "$MON_IFACE" "$DURATION" "$EVENTS"
cleanup
trap - EXIT

if [[ -n "${WIGLE_API_NAME:-}" && -n "${WIGLE_API_TOKEN:-}" && "${WIGLE_API_NAME:-}" != "replace_me" ]]; then
  if ! bash scripts/05_wigle_lookup.sh "$EVENTS" "$RESULTS"; then
    echo "[!] WiGLE lookup failed; continuing to dashboard with captured SSIDs only"
  fi
else
  echo "[!] Skipping WiGLE lookup because credentials are not configured"
fi

bash scripts/06_run_dashboard.sh "$EVENTS" "$RESULTS"
