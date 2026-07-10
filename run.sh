#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

if [[ ! -f .env ]]; then
  echo "[!] .env missing. Run ./setup.sh first." >&2
  exit 1
fi

set -a
# shellcheck disable=SC1091
. ./.env
set +a

if [[ ! -x .venv/bin/python ]] || ! .venv/bin/python -c "import streamlit" >/dev/null 2>&1; then
  echo "[i] Python environment missing. Installing automatically..."
  bash scripts/00_install_kali.sh
fi

IFACE="${1:-${WIFI_INTERFACE:-wlan0}}"
DURATION="${2:-${CAPTURE_DURATION:-60}}"
CHANNEL="${3:-${WIFI_CHANNEL:-6}}"

bash scripts/run_demo.sh "$IFACE" "$DURATION" "$CHANNEL"
