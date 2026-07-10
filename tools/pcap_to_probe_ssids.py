#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
import os
import subprocess
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from beaconghost.normalize_capture import normalize_raw_csv


def main() -> int:
    ap = argparse.ArgumentParser(description="Extract sanitized SSID aggregates from a local PCAP/PCAPNG.")
    ap.add_argument("--pcap", required=True)
    ap.add_argument("--output", required=True)
    ap.add_argument("--source-label", default="pcap_import")
    ap.add_argument("--include-beacons", action="store_true")
    args = ap.parse_args()

    pcap = Path(args.pcap)
    if not pcap.exists():
        raise SystemExit(f"PCAP not found: {pcap}")

    display_filter = "wlan.fc.type_subtype == 4"
    if args.include_beacons:
        display_filter = "wlan.fc.type_subtype == 4 || wlan.fc.type_subtype == 8"

    with tempfile.NamedTemporaryFile(prefix="beaconghost_tshark_", suffix=".csv", delete=False) as tmp:
        raw = tmp.name

    def build_cmd(include_mgt: bool) -> list[str]:
        ssid_fields = ["-e", "wlan.ssid"]
        if include_mgt:
            ssid_fields = ["-e", "wlan_mgt.ssid", "-e", "wlan.ssid"]
        return [
            "tshark", "-r", str(pcap), "-Y", display_filter,
            "-T", "fields", "-E", "header=y", "-E", "separator=,", "-E", "quote=d", "-E", "occurrence=f",
            "-e", "frame.time_epoch",
            "-e", "wlan.fc.type_subtype",
            *ssid_fields,
            "-e", "_ws.col.Info",
            "-e", "radiotap.channel.freq",
            "-e", "radiotap.dbm_antsignal",
        ]

    try:
        with open(raw, "w", encoding="utf-8") as fh:
            try:
                subprocess.run(build_cmd(include_mgt=True), check=True, stdout=fh)
            except subprocess.CalledProcessError:
                fh.seek(0)
                fh.truncate(0)
                subprocess.run(build_cmd(include_mgt=False), check=True, stdout=fh)
        normalize_raw_csv(raw, args.output, source_label=args.source_label, include_beacons=args.include_beacons)
        print(f"Wrote {args.output}")
    finally:
        try:
            os.unlink(raw)
        except OSError:
            pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
