#!/usr/bin/env bash
set -euo pipefail

IFACE="${1:-${MONITOR_INTERFACE:-mon0}}"
DURATION="${2:-10}"

cd "$(dirname "$0")/.."
mkdir -p data/debug
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
RAW="data/debug/debug_tshark_${STAMP}.csv"
OUT="data/debug/debug_ssids_${STAMP}.csv"
FILTER='wlan.fc.type_subtype == 4 || wlan.fc.type_subtype == 8'

TSHARK_MONITOR_ARG=()
IFTYPE="$(iw dev "$IFACE" info 2>/dev/null | awk '/type/ {print $2; exit}' || true)"
if [[ "$IFTYPE" != "monitor" ]]; then
  TSHARK_MONITOR_ARG=(-I)
fi

echo "[+] Capturing ${DURATION}s on $IFACE for SSID decode debug"
if ! sudo tshark -i "$IFACE" "${TSHARK_MONITOR_ARG[@]}" -a "duration:$DURATION" -Y "$FILTER" \
  -T fields -E header=y -E separator=, -E quote=d -E occurrence=f \
  -e frame.time_epoch \
  -e wlan.fc.type_subtype \
  -e wlan_mgt.ssid \
  -e wlan.ssid \
  -e _ws.col.Info \
  -e radiotap.channel.freq \
  -e radiotap.dbm_antsignal > "$RAW"; then
  echo "[!] Debug capture with wlan_mgt.ssid failed; retrying with wlan.ssid only" >&2
  sudo tshark -i "$IFACE" -a "duration:$DURATION" -Y "$FILTER" \
    -T fields -E header=y -E separator=, -E quote=d -E occurrence=f \
    -e frame.time_epoch \
    -e wlan.fc.type_subtype \
    -e wlan.ssid \
    -e _ws.col.Info \
    -e radiotap.channel.freq \
    -e radiotap.dbm_antsignal > "$RAW"
fi

PYTHON_BIN="${PYTHON:-}"
if [[ -z "$PYTHON_BIN" ]]; then
  if [[ ! -x .venv/bin/python ]]; then
    echo "[i] Python virtual environment not found. Installing local dependencies now..."
    bash scripts/ensure_venv.sh
  fi
  PYTHON_BIN=".venv/bin/python"
fi

"$PYTHON_BIN" -m beaconghost.normalize_capture --raw "$RAW" --output "$OUT" --source-label debug --include-beacons

echo "[+] Raw tshark SSID values:"
head -n 20 "$RAW" || true
echo
echo "[+] Normalized SSIDs:"
column -s, -t "$OUT" || cat "$OUT"
