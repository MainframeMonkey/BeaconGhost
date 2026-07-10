#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

echo "[+] Installing Kali packages for passive Wi-Fi capture and BeaconGhost dashboard"
sudo apt update
sudo DEBIAN_FRONTEND=noninteractive apt install -y \
  python3 python3-venv python3-pip \
  tshark wireshark-common \
  iw wireless-tools rfkill usbutils pciutils \
  aircrack-ng

echo "[+] Trying optional Realtek/ALFA DKMS support packages"
if ! sudo DEBIAN_FRONTEND=noninteractive apt install -y linux-headers-$(uname -r) realtek-rtl88xxau-dkms; then
  echo "[i] Optional Realtek DKMS install did not complete. This is OK if your adapter already works."
  echo "[i] Check with: sudo iw dev"
fi

echo "[+] Preparing Python virtual environment and Streamlit"
bash scripts/ensure_venv.sh

chmod +x scripts/*.sh tools/*.py
mkdir -p data/input data/captures data/cache data/results data/debug

echo "[+] Done"
echo "Next: ./setup.sh to enter WiGLE credentials, then ./run.sh"
