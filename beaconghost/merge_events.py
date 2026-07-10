from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from .normalize_capture import OUTPUT_COLUMNS, normalize_event_dataframe


def read_csv(path: str | Path) -> pd.DataFrame:
    path = Path(path)
    if not path.exists() or path.stat().st_size == 0:
        return pd.DataFrame(columns=OUTPUT_COLUMNS)
    df = pd.read_csv(path, dtype=str).fillna("")
    return normalize_event_dataframe(df)


def merge_events(base: str | Path, incoming: str | Path, output: str | Path) -> pd.DataFrame:
    df = pd.concat([read_csv(base), read_csv(incoming)], ignore_index=True)
    if df.empty:
        out = pd.DataFrame(columns=OUTPUT_COLUMNS)
        Path(output).parent.mkdir(parents=True, exist_ok=True)
        out.to_csv(output, index=False)
        return out

    df["seen_count_num"] = pd.to_numeric(df["seen_count"], errors="coerce").fillna(0).astype(int)
    df["sig_min_num"] = pd.to_numeric(df["signal_min_dbm"], errors="coerce")
    df["sig_max_num"] = pd.to_numeric(df["signal_max_dbm"], errors="coerce")

    rows = []
    group_cols = ["frame_type", "ssid", "source_label"]
    for keys, g in df.groupby(group_cols, dropna=False):
        frame_type, ssid, source_label = keys
        firsts = sorted([x for x in g["seen_at"].astype(str).tolist() if x])
        lasts = sorted([x for x in g["last_seen"].astype(str).tolist() if x])
        freqs = set()
        for cell in g["channel_freqs"].astype(str):
            for part in cell.split(";"):
                if part.strip():
                    freqs.add(part.strip())
        sig_min = g["sig_min_num"].dropna()
        sig_max = g["sig_max_num"].dropna()
        rows.append({
            "seen_at": firsts[0] if firsts else "",
            "last_seen": lasts[-1] if lasts else "",
            "frame_type": frame_type,
            "ssid": ssid,
            "source_label": source_label,
            "seen_count": int(g["seen_count_num"].sum()),
            "channel_freqs": ";".join(sorted(freqs)),
            "signal_min_dbm": int(sig_min.min()) if not sig_min.empty else "",
            "signal_max_dbm": int(sig_max.max()) if not sig_max.empty else "",
        })
    out = pd.DataFrame(rows).sort_values(["last_seen", "frame_type", "ssid"], ascending=[False, True, True])
    out = normalize_event_dataframe(out)
    Path(output).parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(output, index=False)
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Merge compact SSID event CSV files.")
    ap.add_argument("--base", required=True)
    ap.add_argument("--incoming", required=True)
    ap.add_argument("--output", required=True)
    args = ap.parse_args(argv)
    merge_events(args.base, args.incoming, args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
