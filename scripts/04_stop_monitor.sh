#!/usr/bin/env bash
set -euo pipefail

MON_IFACE="${1:-${MONITOR_INTERFACE:-mon0}}"

fail() { echo "[!] $*" >&2; exit 1; }
[[ "$(id -u)" -eq 0 ]] || fail "Run with sudo"

if iw dev "$MON_IFACE" info >/dev/null 2>&1; then
  echo "[+] Stopping monitor interface $MON_IFACE" >&2
  ip link set "$MON_IFACE" down || true
  iw dev "$MON_IFACE" del || true
else
  echo "[i] Monitor interface $MON_IFACE not present" >&2
fi
