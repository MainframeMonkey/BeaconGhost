from __future__ import annotations

from pathlib import Path
import pandas as pd


def export_markdown(events_csv: str | Path, results_csv: str | Path, output_md: str | Path) -> None:
    events = pd.read_csv(events_csv, dtype=str).fillna("") if Path(events_csv).exists() else pd.DataFrame()
    results = pd.read_csv(results_csv, dtype=str).fillna("") if Path(results_csv).exists() else pd.DataFrame()
    output_md = Path(output_md)
    output_md.parent.mkdir(parents=True, exist_ok=True)

    lines = []
    lines.append("# BeaconGhost Report")
    lines.append("")
    lines.append("This report contains only SSID-level data. It does not include device MAC addresses or WiGLE BSSIDs.")
    lines.append("")
    lines.append("## Event summary")
    if events.empty:
        lines.append("No events loaded.")
    else:
        summary = events.groupby(["frame_type"]).agg(ssids=("ssid", "nunique"), events=("seen_count", lambda s: pd.to_numeric(s, errors='coerce').fillna(0).sum())).reset_index()
        lines.append(summary.to_markdown(index=False))
    lines.append("")
    lines.append("## WiGLE risk summary")
    if results.empty:
        lines.append("No WiGLE results loaded.")
    else:
        cols = [c for c in ["ssid", "wigle_total", "risk_level", "risk_score", "risk_reason"] if c in results.columns]
        summary = results[cols].drop_duplicates().sort_values(["risk_score", "ssid"], ascending=[False, True])
        lines.append(summary.to_markdown(index=False))
    lines.append("")
    output_md.write_text("\n".join(lines))
