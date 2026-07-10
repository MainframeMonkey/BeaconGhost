#!/usr/bin/env bash
set -euo pipefail

IFACE="${1:-${MONITOR_INTERFACE:-mon0}}"
DURATION="${2:-${CAPTURE_DURATION:-60}}"
OUT="${3:-${EVENTS_CSV:-data/input/ssid_events.csv}}"
SOURCE_LABEL="${SOURCE_LABEL:-beaconghost_lab}"
INCLUDE_BEACONS="${INCLUDE_BEACONS:-true}"

cd "$(dirname "$0")/.."
mkdir -p data/captures "$(dirname "$OUT")"

STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
RAW="data/captures/tshark_fields_${STAMP}.csv"

FILTER="wlan.fc.type_subtype == 4"
BEACON_ARG=""
if [[ "$INCLUDE_BEACONS" == "true" || "$INCLUDE_BEACONS" == "1" || "$INCLUDE_BEACONS" == "yes" ]]; then
  FILTER="wlan.fc.type_subtype == 4 || wlan.fc.type_subtype == 8"
  BEACON_ARG="--include-beacons"
fi

echo "[+] Passive capture on $IFACE for ${DURATION}s"
echo "[+] Filter: $FILTER"
echo "[i] Capturing SSID fields with wlan_mgt.ssid preferred and wlan.ssid as fallback"

TSHARK_MONITOR_ARG=()
IFTYPE="$(iw dev "$IFACE" info 2>/dev/null | awk '/type/ {print $2; exit}' || true)"
if [[ "$IFTYPE" == "monitor" ]]; then
  echo "[i] $IFACE is already type monitor; not passing tshark -I"
else
  echo "[i] $IFACE type is '${IFTYPE:-unknown}'; asking tshark to enable monitor mode with -I"
  TSHARK_MONITOR_ARG=(-I)
fi

capture_with_fields() {
  local mode="$1"
  local ssid_args=()
  if [[ "$mode" == "mgt" ]]; then
    ssid_args=(-e wlan_mgt.ssid -e wlan.ssid)
  else
    ssid_args=(-e wlan.ssid)
  fi

  sudo tshark -i "$IFACE" "${TSHARK_MONITOR_ARG[@]}" -a "duration:$DURATION" -Y "$FILTER" \
    -T fields -E header=y -E separator=, -E quote=d -E occurrence=f \
    -e frame.time_epoch \
    -e wlan.fc.type_subtype \
    "${ssid_args[@]}" \
    -e _ws.col.Info \
    -e radiotap.channel.freq \
    -e radiotap.dbm_antsignal > "$RAW"
}

if ! capture_with_fields mgt; then
  echo "[!] tshark failed with wlan_mgt.ssid or current monitor args; retrying safer fallback" >&2
  if [[ "${#TSHARK_MONITOR_ARG[@]}" -gt 0 ]]; then
    TSHARK_MONITOR_ARG=()
  fi
  if ! capture_with_fields mgt; then
    echo "[!] tshark still failed with wlan_mgt.ssid; retrying with wlan.ssid only" >&2
    capture_with_fields legacy
  fi
fi

PYTHON_BIN="${PYTHON:-}"
if [[ -z "$PYTHON_BIN" ]]; then
  if [[ ! -x .venv/bin/python ]]; then
    echo "[i] Python virtual environment not found. Installing local dependencies now..."
    bash scripts/ensure_venv.sh
  fi
  PYTHON_BIN=".venv/bin/python"
fi

"$PYTHON_BIN" -m beaconghost.normalize_capture \
  --raw "$RAW" \
  --output "$OUT" \
  --source-label "$SOURCE_LABEL" \
  $BEACON_ARG

echo "[+] Wrote sanitized events: $OUT"
echo "[i] Raw tshark field CSV kept at: $RAW"
echo "[i] It contains SSID-related fields only, not MAC fields. Delete it after the run if not needed."
