#!/usr/bin/env bash
set -euo pipefail

IFACE="${1:-${WIFI_INTERFACE:-}}"

cd "$(dirname "$0")/.."

fail() { echo "[!] $*" >&2; exit 1; }
need() { command -v "$1" >/dev/null 2>&1 || fail "Missing command: $1"; }

need iw
need ip
need tshark
need python3

if [[ -z "$IFACE" ]]; then
  echo "[i] Wireless interfaces seen by iw:"
  sudo iw dev || true
  fail "No interface given. Example: bash scripts/01_preflight.sh wlan1"
fi

sudo iw dev "$IFACE" info >/dev/null 2>&1 || fail "Interface not found by iw: $IFACE"

echo "[+] Interface $IFACE exists"
echo "[+] Interface info:"
sudo iw dev "$IFACE" info || true

echo "[+] Checking supported interface modes"
if sudo iw list | grep -A 20 "Supported interface modes" | grep -q "monitor"; then
  echo "[+] Monitor mode appears supported by at least one phy"
else
  echo "[!] Could not confirm monitor mode from iw list. The adapter/driver may still work, but check manually."
fi

if [[ -f .env ]]; then
  set -a
  # shellcheck disable=SC1091
  . ./.env
  set +a
fi

if [[ -z "${WIGLE_API_NAME:-}" || -z "${WIGLE_API_TOKEN:-}" || "${WIGLE_API_NAME:-}" == "replace_me" ]]; then
  echo "[!] WiGLE credentials not configured yet. Capture will work; lookup will not."
else
  echo "[+] WiGLE environment variables are set"
fi

echo "[+] BeaconGhost ready"
