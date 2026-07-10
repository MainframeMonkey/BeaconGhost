#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

if [[ -f .env ]]; then
  set -a
  # shellcheck disable=SC1091
  . ./.env
  set +a
fi

IFACE="${1:-${WIFI_INTERFACE:-}}"
CHUNK="${2:-30}"
CHANNELS="${CHANNEL_HOP_LIST:-1 6 11 36 40 44 48}"
EVENTS="${EVENTS_CSV:-data/input/ssid_events.csv}"
RESULTS="${WIGLE_RESULTS_CSV:-data/results/wigle_results.csv}"
PYTHON_BIN="${PYTHON:-}"
if [[ -z "$PYTHON_BIN" ]]; then
  if [[ ! -x .venv/bin/python ]]; then
    echo "[i] Python virtual environment not found. Installing local dependencies now..."
    bash scripts/ensure_venv.sh
  fi
  PYTHON_BIN=".venv/bin/python"
fi

if [[ -z "$IFACE" ]]; then
  echo "Usage: bash scripts/run_live_demo.sh <wireless_interface> [chunk_seconds]" >&2
  exit 1
fi

bash scripts/01_preflight.sh "$IFACE"
MON_IFACE="$(sudo -E bash scripts/02_start_monitor.sh "$IFACE" "" | tail -n 1)"
cleanup() {
  sudo pkill -f "scripts/channel_hop.sh $MON_IFACE" >/dev/null 2>&1 || true
  sudo -E bash scripts/04_stop_monitor.sh "$MON_IFACE" || true
}
trap cleanup EXIT

sudo -E bash scripts/channel_hop.sh "$MON_IFACE" 2 "$CHANNELS" &
HOP_PID=$!
echo "[+] Channel hopper PID: $HOP_PID"

touch "$EVENTS"
while true; do
  TMP="data/input/live_chunk_$(date -u +%Y%m%dT%H%M%SZ).csv"
  bash scripts/03_capture_ssids.sh "$MON_IFACE" "$CHUNK" "$TMP"
  "$PYTHON_BIN" -m beaconghost.merge_events --base "$EVENTS" --incoming "$TMP" --output "$EVENTS"
  rm -f "$TMP"
  if [[ -n "${WIGLE_API_NAME:-}" && -n "${WIGLE_API_TOKEN:-}" && "${WIGLE_API_NAME:-}" != "replace_me" ]]; then
    bash scripts/05_wigle_lookup.sh "$EVENTS" "$RESULTS" || echo "[!] WiGLE lookup failed; continuing capture loop"
  fi
  echo "[+] Updated $EVENTS and $RESULTS"
done
