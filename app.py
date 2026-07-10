from __future__ import annotations

import argparse
import base64
import os
from pathlib import Path

import altair as alt
import folium
from folium.plugins import MarkerCluster
import pandas as pd
import streamlit as st
from dotenv import load_dotenv
from streamlit_folium import st_folium

try:
    from streamlit_autorefresh import st_autorefresh
except Exception:  # pragma: no cover
    st_autorefresh = None

from beaconghost.risk import score_ssid
from beaconghost.ssid_utils import clean_ssid
from beaconghost.wigle_client import lookup_events

load_dotenv()

st.set_page_config(page_title="BeaconGhost", page_icon="assets/favicon.png", layout="wide")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--events", default=os.getenv("EVENTS_CSV", "data/input/ssid_events.csv"))
    parser.add_argument("--results", default=os.getenv("WIGLE_RESULTS_CSV", "data/results/wigle_results.csv"))
    args, _ = parser.parse_known_args()
    return args


EVENT_COLUMNS = [
    "seen_at", "last_seen", "frame_type", "ssid", "source_label",
    "seen_count", "channel_freqs", "signal_min_dbm", "signal_max_dbm",
]

RESULT_COLUMNS = [
    "ssid", "wigle_total", "returned_index", "lat_display", "lon_display",
    "city", "region", "country", "firsttime", "lasttime", "encryption",
    "risk_level", "risk_score", "risk_reason", "lookup_mode", "lookup_status",
    "error", "looked_up_at",
]


def read_csv(path: str | Path, allowed_columns: list[str] | None = None) -> pd.DataFrame:
    p = Path(path)
    if not p.exists() or p.stat().st_size == 0:
        return pd.DataFrame(columns=allowed_columns or [])
    df = pd.read_csv(p, dtype=str).fillna("")
    if "ssid" in df.columns:
        df["ssid"] = df["ssid"].map(clean_ssid)
    if allowed_columns is not None:
        for col in allowed_columns:
            if col not in df.columns:
                df[col] = ""
        df = df[allowed_columns]
    return df


def metric_int(value) -> int:
    try:
        return int(float(value))
    except Exception:
        return 0


def asset_data_uri(path: str | Path) -> str:
    p = Path(path)
    if not p.exists():
        return ""
    try:
        data = base64.b64encode(p.read_bytes()).decode("ascii")
        suffix = p.suffix.lower().lstrip(".") or "png"
        if suffix == "jpg":
            suffix = "jpeg"
        return f"data:image/{suffix};base64,{data}"
    except Exception:
        return ""


def add_missing_risk(results: pd.DataFrame) -> pd.DataFrame:
    if results.empty:
        return results
    df = results.copy()
    if "risk_level" not in df.columns or "risk_score" not in df.columns:
        rows = []
        for _, row in df.iterrows():
            risk = score_ssid(row.get("ssid", ""), metric_int(row.get("wigle_total", 0)))
            rows.append(risk)
        df["risk_level"] = [r.level for r in rows]
        df["risk_score"] = [r.score for r in rows]
        df["risk_reason"] = [r.reason for r in rows]
    return df


SOURCE_FILTERS = {
    "Probe requests only": "probe_request",
    "Beacons only": "beacon",
    "All SSIDs": "all",
}


def default_source_filter_index() -> int:
    wanted = os.getenv("DASHBOARD_SOURCE_FILTER", "probe_request").strip().lower()
    aliases = {
        "probe": "probe_request",
        "probes": "probe_request",
        "probe_request": "probe_request",
        "probe_requests": "probe_request",
        "beacon": "beacon",
        "beacons": "beacon",
        "all": "all",
        "any": "all",
        "*": "all",
    }
    wanted = aliases.get(wanted, wanted)
    values = list(SOURCE_FILTERS.values())
    return values.index(wanted) if wanted in values else 0


def filter_events_by_source(events: pd.DataFrame, source_filter: str) -> pd.DataFrame:
    if events.empty or source_filter in {"", "all", "any", "*"} or "frame_type" not in events.columns:
        return events.copy()
    return events[events["frame_type"].astype(str).str.lower().eq(source_filter)].copy()


def filter_results_by_source(results: pd.DataFrame, events: pd.DataFrame, source_filter: str) -> pd.DataFrame:
    if results.empty or source_filter in {"", "all", "any", "*"}:
        return results.copy()
    filtered_events = filter_events_by_source(events, source_filter)
    if filtered_events.empty or "ssid" not in filtered_events.columns or "ssid" not in results.columns:
        return results.iloc[0:0].copy()
    ssids = {s.strip() for s in filtered_events["ssid"].astype(str).tolist() if s.strip()}
    return results[results["ssid"].astype(str).isin(ssids)].copy()


def dashboard_css() -> None:
    st.markdown(
        """
        <style>
        .stApp { background: radial-gradient(circle at top left, #16202a 0, #0b0f14 45%, #05070a 100%); }
        .block-container { padding-top: 1.4rem; }
        .hero {
            padding: 1.2rem 1.4rem; border: 1px solid rgba(255,255,255,0.12);
            border-radius: 22px; background: rgba(255,255,255,0.05); backdrop-filter: blur(8px);
            margin-bottom: 1rem; display: flex; align-items: center; gap: 1rem; overflow: hidden;
        }
        .hero-logo { width: min(980px, 100%); max-height: 245px; height: auto; object-fit: contain; display:block; }
        .hero-avatar { width: 74px; height: 74px; border-radius: 16px; object-fit: cover;
            background: rgba(0,0,0,0.35); border: 1px solid rgba(76,255,71,0.30); }
        .hero h1 { margin: 0; font-size: 2.15rem; }
        .hero p { margin: 0.3rem 0 0 0; color: rgba(255,255,255,0.78); }
        .hero small { color: rgba(76,255,71,0.78); letter-spacing: 0.05em; text-transform: uppercase; }
        .scope-box {
            padding: 0.9rem 1rem; border-radius: 16px; background: rgba(52, 152, 219, 0.10);
            border: 1px solid rgba(52, 152, 219, 0.25); color: rgba(255,255,255,0.88);
            margin-bottom: 1rem;
        }
        .warn-box {
            padding: 0.9rem 1rem; border-radius: 16px; background: rgba(241, 196, 15, 0.10);
            border: 1px solid rgba(241, 196, 15, 0.25); color: rgba(255,255,255,0.88);
            margin-bottom: 1rem;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_map(results: pd.DataFrame) -> None:
    if results.empty or "lat_display" not in results.columns or "lon_display" not in results.columns:
        st.info("No map data yet. Run a WiGLE lookup after capturing SSIDs.")
        return

    df = results.copy()
    df["lat"] = pd.to_numeric(df["lat_display"], errors="coerce")
    df["lon"] = pd.to_numeric(df["lon_display"], errors="coerce")
    df = df.dropna(subset=["lat", "lon"])
    if df.empty:
        st.info("WiGLE returned no display coordinates for the current data.")
        return

    center = [float(df["lat"].mean()), float(df["lon"].mean())]
    m = folium.Map(location=center, zoom_start=6, tiles="CartoDB dark_matter")
    cluster = MarkerCluster(name="SSID indicators").add_to(m)

    for _, row in df.iterrows():
        popup = folium.Popup(
            html=(
                f"<b>SSID:</b> {row.get('ssid','')}<br>"
                f"<b>Risk:</b> {row.get('risk_level','')} ({row.get('risk_score','')})<br>"
                f"<b>WiGLE total:</b> {row.get('wigle_total','')}<br>"
                f"<b>Place:</b> {row.get('city','')} {row.get('region','')} {row.get('country','')}<br>"
                f"<b>Note:</b> rounded display coordinate"
            ),
            max_width=360,
        )
        folium.CircleMarker(
            location=[float(row["lat"]), float(row["lon"])],
            radius=6 + min(metric_int(row.get("risk_score", 0)) / 20.0, 6),
            fill=True,
            fill_opacity=0.75,
            popup=popup,
            tooltip=f"{row.get('ssid','')} | {row.get('risk_level','')}",
        ).add_to(cluster)
    st_folium(m, width=None, height=560)


def main() -> None:
    args = parse_args()
    dashboard_css()

    refresh_seconds = metric_int(os.getenv("DASHBOARD_REFRESH_SECONDS", "0"))
    if st_autorefresh and refresh_seconds > 0:
        st_autorefresh(interval=refresh_seconds * 1000, key="beaconghost_autorefresh")

    logo_uri = asset_data_uri("assets/beaconghost_dashboard_header_clean.png")
    avatar_uri = asset_data_uri("assets/avatar.png")
    if logo_uri:
        hero_inner = f'<img class="hero-logo" src="{logo_uri}" alt="BeaconGhost logo" />'
    else:
        avatar_html = f'<img class="hero-avatar" src="{avatar_uri}" alt="BeaconGhost avatar" />' if avatar_uri else ""
        hero_inner = f'''{avatar_html}<div><small>by M@infr@meMonkey</small><h1>BeaconGhost</h1><p>BeaconGhost demonstrates how remembered WiFi networks can expose location traces when correlated with public WiFi geolocation data.</p></div>'''
    st.markdown(
        f"""
        <div class="hero">
            {hero_inner}
        </div>
        """,
        unsafe_allow_html=True,
    )

    with st.sidebar:
        logo = Path("assets/beaconghost_icon.png")
        if logo.exists():
            st.image(str(logo), width=120)
        else:
            avatar = Path("assets/avatar.png")
            if avatar.exists():
                st.image(str(avatar), width=120)
        st.header("BeaconGhost")
        st.caption("by M@infr@meMonkey")
        events_path = st.text_input("Events CSV", args.events)
        results_path = st.text_input("WiGLE results CSV", args.results)
        source_filter_label = st.selectbox(
            "SSID source filter",
            list(SOURCE_FILTERS.keys()),
            index=default_source_filter_index(),
            help="Probe requests are remembered-network probes from devices. Beacons are nearby access points.",
        )
        source_filter = SOURCE_FILTERS[source_filter_label]
        do_lookup = st.button(f"Run WiGLE lookup ({source_filter_label.lower()})", type="primary")

    events = read_csv(events_path, EVENT_COLUMNS)
    results = add_missing_risk(read_csv(results_path, RESULT_COLUMNS))

    # Manual display filter only.
    events_for_view = filter_events_by_source(events, source_filter)
    results_for_view = filter_results_by_source(results, events, source_filter)

    if do_lookup:
        api_name = os.getenv("WIGLE_API_NAME", "").strip()
        api_token = os.getenv("WIGLE_API_TOKEN", "").strip()
        if not api_name or not api_token or api_name == "replace_me" or api_token == "replace_me":
            st.error("Missing WiGLE credentials. Set WIGLE_API_NAME and WIGLE_API_TOKEN in .env.")
        else:
            with st.spinner("Looking up SSIDs via WiGLE..."):
                lookup_events(
                    events_path,
                    results_path,
                    os.getenv("WIGLE_CACHE", "data/cache/wigle_cache.json"),
                    api_name=api_name,
                    api_token=api_token,
                    frame_type=source_filter,
                    max_results_per_ssid=metric_int(os.getenv("WIGLE_MAX_RESULTS_PER_SSID", "10")),
                    sleep_seconds=float(os.getenv("WIGLE_SLEEP_SECONDS", "2.0")),
                    coord_precision=metric_int(os.getenv("WIGLE_COORD_PRECISION", "3")),
                    mode=os.getenv("WIGLE_LOOKUP_MODE", "exact"),
                    use_cache=True,
                    max_new_lookups=metric_int(os.getenv("WIGLE_MAX_NEW_LOOKUPS_PER_RUN", "10")),
                )
            st.success("WiGLE lookup completed or partially completed. Refreshing dashboard data.")
            st.rerun()

    c1, c2, c3, c4, c5 = st.columns(5)
    st.caption(f"Current source filter: {source_filter_label}")
    unique_ssids = events_for_view["ssid"].nunique() if not events_for_view.empty and "ssid" in events_for_view.columns else 0
    probe_rows = len(events_for_view[events_for_view["frame_type"].eq("probe_request")]) if not events_for_view.empty and "frame_type" in events_for_view.columns else 0
    beacon_rows = len(events_for_view[events_for_view["frame_type"].eq("beacon")]) if not events_for_view.empty and "frame_type" in events_for_view.columns else 0
    result_ssids = results_for_view["ssid"].nunique() if not results_for_view.empty and "ssid" in results_for_view.columns else 0
    high_ssids = results_for_view[results_for_view["risk_level"].eq("high")]["ssid"].nunique() if not results_for_view.empty and "risk_level" in results_for_view.columns else 0
    c1.metric("Unique SSIDs", unique_ssids)
    c2.metric("Probe SSIDs", probe_rows)
    c3.metric("Beacon SSIDs", beacon_rows)
    c4.metric("WiGLE SSIDs", result_ssids)
    c5.metric("High risk", high_ssids)

    tab_map, tab_events, tab_risk, tab_results, tab_notes = st.tabs(["Map", "SSID feed", "Risk", "WiGLE rows", "Notes"])

    with tab_map:
        render_map(results_for_view)

    with tab_events:
        if events_for_view.empty:
            st.info("No sanitized SSID events loaded yet for the selected source filter.")
        else:
            sort_cols = [c for c in ["last_seen", "frame_type", "ssid"] if c in events_for_view.columns]
            if sort_cols:
                asc = [False] + [True] * (len(sort_cols) - 1)
                show = events_for_view.sort_values(sort_cols, ascending=asc)
            else:
                show = events_for_view
            st.dataframe(show, use_container_width=True, hide_index=True)

    with tab_risk:
        if results_for_view.empty:
            st.info("No WiGLE risk data yet.")
        else:
            summary_cols = ["ssid", "wigle_total", "risk_level", "risk_score", "risk_reason"]
            summary = results_for_view[[c for c in summary_cols if c in results_for_view.columns]].drop_duplicates()
            if "risk_score" in summary.columns:
                summary["risk_score_num"] = pd.to_numeric(summary["risk_score"], errors="coerce").fillna(0)
                summary = summary.sort_values(["risk_score_num", "ssid"], ascending=[False, True]).drop(columns=["risk_score_num"])
            st.dataframe(summary, use_container_width=True, hide_index=True)

            chart_df = summary.copy()
            if "risk_level" in chart_df.columns:
                counts = chart_df.groupby("risk_level", as_index=False).size().rename(columns={"size": "count"})
                chart = alt.Chart(counts).mark_bar().encode(
                    x=alt.X("risk_level:N", sort=["high", "medium", "low", "none"], title="Risk level"),
                    y=alt.Y("count:Q", title="SSID count"),
                    tooltip=["risk_level", "count"],
                )
                st.altair_chart(chart, use_container_width=True)

    with tab_results:
        if results_for_view.empty:
            st.info("No WiGLE rows loaded yet.")
        else:
            safe_cols = [
                "ssid", "wigle_total", "returned_index", "lat_display", "lon_display",
                "city", "region", "country", "firsttime", "lasttime", "encryption",
                "risk_level", "risk_score", "lookup_mode", "lookup_status", "error", "looked_up_at",
            ]
            st.dataframe(results_for_view[[c for c in safe_cols if c in results_for_view.columns]], use_container_width=True, hide_index=True)

    with tab_notes:
        st.markdown(
            """
            ### BeaconGhost interpretation

            Probe requests can reveal SSIDs that a device is looking for. A rare SSID may be a location hint if it appears in a public Wi-Fi database. A common SSID is usually weak evidence. Use the sidebar source filter to switch the map between probe requests, beacons, and all SSIDs.

            This dashboard is intentionally SSID-level. It does not need client MAC addresses, BSSIDs, credentials, deauthentication, association, or packet injection to demonstrate the privacy issue.

            ### Practical mitigations

            - Forget old Wi-Fi networks you no longer need.
            - Avoid hidden SSIDs when the goal is privacy.
            - Keep private Wi-Fi address / MAC randomization enabled.
            - Check old IoT and legacy devices separately.
            - Treat WiGLE results as indicators, not proof.
            """
        )


if __name__ == "__main__":
    main()
