#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
bash scripts/00_install_kali.sh
if [[ ! -f .env ]]; then
  cp .env.example .env
  chmod 600 .env
  echo "[i] Created .env. Edit WIGLE_API_NAME and WIGLE_API_TOKEN before running ./run.sh"
fi
