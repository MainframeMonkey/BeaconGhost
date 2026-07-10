#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

if ! command -v python3 >/dev/null 2>&1; then
  echo "[!] python3 not found. Run: sudo apt update && sudo apt install -y python3 python3-venv python3-pip" >&2
  exit 1
fi

if [[ ! -d .venv ]]; then
  echo "[+] Creating Python virtual environment: .venv"
  if ! python3 -m venv .venv; then
    echo "[!] python3 venv creation failed. Installing python3-venv and python3-pip, then retrying." >&2
    sudo apt update
    sudo DEBIAN_FRONTEND=noninteractive apt install -y python3-venv python3-pip
    python3 -m venv .venv
  fi
fi

# shellcheck disable=SC1091
. .venv/bin/activate

python -m pip install --upgrade pip wheel setuptools
python -m pip install --upgrade -r requirements.txt

python - <<'PY'
import importlib
for module in ["streamlit", "pandas", "folium", "streamlit_folium", "dotenv"]:
    importlib.import_module(module)
print("[+] Python environment ready")
PY
