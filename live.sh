#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
if [[ -f .env ]]; then
  set -a
  # shellcheck disable=SC1091
  . ./.env
  set +a
fi
bash scripts/run_live_demo.sh "${WIFI_INTERFACE:-wlan0}" "${CAPTURE_DURATION:-30}"
