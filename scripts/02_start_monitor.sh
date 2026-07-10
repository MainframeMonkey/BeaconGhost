#!/usr/bin/env bash
set -euo pipefail

IFACE="${1:-${WIFI_INTERFACE:-}}"
CHANNEL="${2:-${WIFI_CHANNEL:-}}"
MON_IFACE="${MONITOR_INTERFACE:-mon0}"

fail() { echo "[!] $*" >&2; exit 1; }
[[ -n "$IFACE" ]] || fail "Usage: sudo bash scripts/02_start_monitor.sh <interface> [channel]"
[[ "$(id -u)" -eq 0 ]] || fail "Run with sudo"

command -v iw >/dev/null 2>&1 || fail "iw missing"
command -v ip >/dev/null 2>&1 || fail "ip missing"

iw dev "$IFACE" info >/dev/null 2>&1 || fail "Interface not found: $IFACE"
PHY="$(iw dev "$IFACE" info | awk '/wiphy/ {print "phy"$2; exit}')"
[[ -n "$PHY" ]] || fail "Could not determine phy for $IFACE"

if iw dev "$MON_IFACE" info >/dev/null 2>&1; then
  echo "[i] Existing $MON_IFACE found; deleting it first" >&2
  ip link set "$MON_IFACE" down || true
  iw dev "$MON_IFACE" del || true
fi

echo "[+] Creating monitor interface $MON_IFACE on $PHY" >&2
iw phy "$PHY" interface add "$MON_IFACE" type monitor
ip link set "$MON_IFACE" up

if [[ -n "$CHANNEL" ]]; then
  echo "[+] Setting $MON_IFACE to channel $CHANNEL" >&2
  iw dev "$MON_IFACE" set channel "$CHANNEL" || echo "[!] Could not set channel $CHANNEL" >&2
fi

echo "[+] Monitor interface ready: $MON_IFACE" >&2
echo "$MON_IFACE"
