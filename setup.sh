#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

echo "[+] BeaconGhost Kali-only setup"

bash scripts/00_install_kali.sh

if [[ ! -f .env ]]; then
  cp .env.example .env
fi

current_name=""
current_token=""
if [[ -f .env ]]; then
  current_name="$(grep -E '^WIGLE_API_NAME=' .env | head -n1 | cut -d= -f2- || true)"
  current_token="$(grep -E '^WIGLE_API_TOKEN=' .env | head -n1 | cut -d= -f2- || true)"
fi

echo
read -r -p "WiGLE API Name: " api_name
read -r -s -p "WiGLE API Token: " api_token
echo

if [[ -z "$api_name" || -z "$api_token" ]]; then
  echo "[!] API Name and API Token are required." >&2
  exit 1
fi

python3 - "$api_name" "$api_token" <<'PY'
from pathlib import Path
import sys
api_name, api_token = sys.argv[1], sys.argv[2]
path = Path('.env')
lines = path.read_text().splitlines() if path.exists() else []
keys = {
    'WIGLE_API_NAME': api_name,
    'WIGLE_API_TOKEN': api_token,
}
seen = set()
out = []
for line in lines:
    if '=' in line and not line.lstrip().startswith('#'):
        key = line.split('=', 1)[0].strip()
        if key in keys:
            out.append(f'{key}={keys[key]}')
            seen.add(key)
            continue
    out.append(line)
for key, value in keys.items():
    if key not in seen:
        out.append(f'{key}={value}')
path.write_text('\n'.join(out).rstrip() + '\n')
PY

chmod 600 .env

echo "[+] Setup complete"
echo "[+] Run: ./run.sh"
