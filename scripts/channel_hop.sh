#!/usr/bin/env bash
set -euo pipefail

IFACE="${1:-${MONITOR_INTERFACE:-mon0}}"
DWELL="${2:-2}"
CHANNELS="${3:-1 6 11 36 40 44 48}"

fail() { echo "[!] $*" >&2; exit 1; }
[[ "$(id -u)" -eq 0 ]] || fail "Run with sudo"

trap 'echo "[i] Channel hopper stopped" >&2' EXIT

echo "[+] Passive channel hopping on $IFACE every ${DWELL}s: $CHANNELS" >&2
while true; do
  for ch in $CHANNELS; do
    iw dev "$IFACE" set channel "$ch" >/dev/null 2>&1 || true
    sleep "$DWELL"
  done
done
