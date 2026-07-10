#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pandas as pd

from beaconghost.normalize_capture import OUTPUT_COLUMNS, normalize_event_dataframe
from beaconghost.ssid_utils import clean_ssid


def fix_csv(input_csv: Path, output_csv: Path, compact: bool = True) -> None:
    if not input_csv.exists():
        raise SystemExit(f"Input CSV not found: {input_csv}")
    df = pd.read_csv(input_csv, dtype=str).fillna("")
    if "ssid" not in df.columns:
        raise SystemExit("CSV has no ssid column")

    before = df["ssid"].astype(str).tolist()
    if compact:
        df = normalize_event_dataframe(df)
    else:
        df["ssid"] = df["ssid"].map(clean_ssid)
        df = df[df["ssid"].astype(str).str.strip().ne("")].copy()

    after = df["ssid"].astype(str).tolist() if "ssid" in df.columns else []
    changed = sum(1 for a, b in zip(before, after) if a != b)

    output_csv.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output_csv, index=False)
    print(f"[+] Wrote {output_csv}")
    print(f"[+] Cleaned SSID cells: {changed}")
    if not df.empty:
        cols = [c for c in ["frame_type", "ssid", "seen_count", "channel_freqs", "signal_min_dbm", "signal_max_dbm"] if c in df.columns]
        print(df[cols].head(30).to_string(index=False))


def main() -> int:
    ap = argparse.ArgumentParser(description="Decode hex-byte SSIDs in an existing CSV.")
    ap.add_argument("input_csv", help="Existing CSV with an ssid column")
    ap.add_argument("output_csv", nargs="?", help="Output CSV. Defaults to overwriting the input after creating a backup")
    ap.add_argument("--keep-extra-columns", action="store_true", help="Keep non-standard columns instead of writing compact event columns")
    args = ap.parse_args()

    input_csv = Path(args.input_csv)
    if args.output_csv:
        output_csv = Path(args.output_csv)
    else:
        backup = input_csv.with_suffix(input_csv.suffix + ".backup.csv")
        if input_csv.exists() and not backup.exists():
            backup.write_bytes(input_csv.read_bytes())
            print(f"[+] Backup written: {backup}")
        output_csv = input_csv

    fix_csv(input_csv, output_csv, compact=not args.keep_extra_columns)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
