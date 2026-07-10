from __future__ import annotations

import argparse
import csv
import math
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from .ssid_utils import best_ssid, clean_ssid, ssid_from_info_column

SUBTYPE_MAP = {
    "4": "probe_request",
    "0x0004": "probe_request",
    "8": "beacon",
    "0x0008": "beacon",
}

OUTPUT_COLUMNS = [
    "seen_at", "last_seen", "frame_type", "ssid", "source_label",
    "seen_count", "channel_freqs", "signal_min_dbm", "signal_max_dbm",
]

RAW_FIELD_COLUMNS = [
    "frame.time_epoch",
    "wlan.fc.type_subtype",
    "wlan_mgt.ssid",
    "wlan.ssid",
    "_ws.col.Info",
    "radiotap.channel.freq",
    "radiotap.dbm_antsignal",
]


def iso_from_epoch(value: str) -> str:
    try:
        ts = float(value)
        if math.isnan(ts) or ts <= 0:
            raise ValueError
        return datetime.fromtimestamp(ts, tz=timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    except Exception:
        return datetime.now(tz=timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def empty_output(output_csv: str | Path) -> pd.DataFrame:
    out = pd.DataFrame(columns=OUTPUT_COLUMNS)
    Path(output_csv).parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(output_csv, index=False)
    return out


def normalize_event_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """Clean an already aggregated event DataFrame and keep compact columns only."""
    out = df.copy()
    for col in OUTPUT_COLUMNS:
        if col not in out.columns:
            out[col] = ""
    out["ssid"] = out["ssid"].map(clean_ssid)
    out = out[out["ssid"].astype(str).str.strip().ne("")].copy()
    return out[OUTPUT_COLUMNS]


def normalize_event_csv(input_csv: str | Path, output_csv: str | Path | None = None) -> pd.DataFrame:
    input_csv = Path(input_csv)
    output_csv = Path(output_csv) if output_csv is not None else input_csv
    if not input_csv.exists() or input_csv.stat().st_size == 0:
        return empty_output(output_csv)
    df = pd.read_csv(input_csv, dtype=str, keep_default_na=False).fillna("")
    out = normalize_event_dataframe(df)
    output_csv.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(output_csv, index=False)
    return out


def normalize_raw_csv(
    raw_csv: str | Path,
    output_csv: str | Path,
    source_label: str = "beaconghost_lab",
    include_beacons: bool = True,
) -> pd.DataFrame:
    raw_csv = Path(raw_csv)
    output_csv = Path(output_csv)
    output_csv.parent.mkdir(parents=True, exist_ok=True)

    if not raw_csv.exists() or raw_csv.stat().st_size == 0:
        return empty_output(output_csv)

    df = pd.read_csv(raw_csv, dtype=str, keep_default_na=False, quoting=csv.QUOTE_MINIMAL).fillna("")

    col_epoch = "frame.time_epoch"
    col_subtype = "wlan.fc.type_subtype"
    col_ssid_mgt = "wlan_mgt.ssid"
    col_ssid = "wlan.ssid"
    col_info = "_ws.col.Info"
    col_freq = "radiotap.channel.freq"
    col_signal = "radiotap.dbm_antsignal"

    for col in [col_epoch, col_subtype, col_ssid_mgt, col_ssid, col_info, col_freq, col_signal]:
        if col not in df.columns:
            df[col] = ""

    df["frame_type"] = df[col_subtype].astype(str).str.strip().map(SUBTYPE_MAP).fillna("other")
    if include_beacons:
        df = df[df["frame_type"].isin(["probe_request", "beacon"])]
    else:
        df = df[df["frame_type"].eq("probe_request")]

    if df.empty:
        return empty_output(output_csv)

    df["ssid"] = df.apply(
        lambda row: best_ssid(
            row.get(col_ssid_mgt, ""),
            row.get(col_ssid, ""),
            ssid_from_info_column(row.get(col_info, "")),
        ),
        axis=1,
    )
    df = df[df["ssid"].astype(str).str.strip().ne("")].copy()
    if df.empty:
        return empty_output(output_csv)

    df["seen_at_raw"] = df[col_epoch].map(iso_from_epoch)
    df["freq"] = df[col_freq].astype(str).str.extract(r"(\d+)", expand=False).fillna("")
    df["signal"] = pd.to_numeric(df[col_signal].astype(str).str.extract(r"(-?\d+)", expand=False), errors="coerce")
    df["source_label"] = source_label

    rows = []
    group_cols = ["frame_type", "ssid", "source_label"]
    for (frame_type, ssid, src), g in df.groupby(group_cols, dropna=False):
        times = sorted(g["seen_at_raw"].dropna().astype(str).tolist())
        freqs = sorted({x for x in g["freq"].dropna().astype(str).tolist() if x})
        sig = g["signal"].dropna()
        rows.append({
            "seen_at": times[0] if times else "",
            "last_seen": times[-1] if times else "",
            "frame_type": frame_type,
            "ssid": clean_ssid(ssid),
            "source_label": src,
            "seen_count": int(len(g)),
            "channel_freqs": ";".join(freqs),
            "signal_min_dbm": int(sig.min()) if not sig.empty else "",
            "signal_max_dbm": int(sig.max()) if not sig.empty else "",
        })

    out = pd.DataFrame(rows).sort_values(["frame_type", "ssid"]).reset_index(drop=True)
    out = normalize_event_dataframe(out)
    out.to_csv(output_csv, index=False)
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Normalize TShark SSID field output into a compact aggregate CSV.")
    ap.add_argument("--raw", required=True, help="Raw TShark field CSV")
    ap.add_argument("--output", required=True, help="Compact output CSV")
    ap.add_argument("--source-label", default="beaconghost_lab")
    ap.add_argument("--include-beacons", action="store_true")
    args = ap.parse_args(argv)
    normalize_raw_csv(
        args.raw,
        args.output,
        source_label=args.source_label,
        include_beacons=args.include_beacons,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
