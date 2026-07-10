#!/usr/bin/env bash
set -euo pipefail
IFACE="${1:-${MONITOR_INTERFACE:-mon0}}"
DURATION="${2:-10}"
cd "$(dirname "$0")/.."
echo "[+] Interface details"
iw dev "$IFACE" info || true
echo
echo "[+] TShark interfaces"
tshark -D || true
echo
echo "[+] Test capture without tshark -I on $IFACE for ${DURATION}s"
sudo tshark -i "$IFACE" -a "duration:$DURATION" \
  -T fields -E header=y -E separator=, -E quote=d -E occurrence=f \
  -e frame.number -e frame.time_epoch -e wlan.fc.type_subtype -e wlan_mgt.ssid -e wlan.ssid -e _ws.col.Info -e radiotap.channel.freq \
  | sed -n '1,25p'
