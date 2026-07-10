from __future__ import annotations

import argparse
import json
import os
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
import requests
from dotenv import load_dotenv

from .risk import score_ssid
from .ssid_utils import clean_ssid

API_URL = "https://api.wigle.net/api/v2/network/search"

OUTPUT_COLUMNS = [
    "ssid", "wigle_total", "returned_index", "lat_display", "lon_display",
    "city", "region", "country", "firsttime", "lasttime", "encryption",
    "risk_level", "risk_score", "risk_reason", "lookup_mode", "lookup_status",
    "error", "looked_up_at",
]


@dataclass
class RateLimitError(RuntimeError):
    message: str
    retry_after: str = ""

    def __str__(self) -> str:
        if self.retry_after:
            return f"{self.message} retry_after={self.retry_after}s"
        return self.message


class AuthenticationError(RuntimeError):
    pass


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def load_cache(path: str | Path) -> dict[str, Any]:
    p = Path(path)
    if not p.exists() or p.stat().st_size == 0:
        return {}
    try:
        return json.loads(p.read_text())
    except Exception:
        return {}


def save_cache(path: str | Path, cache: dict[str, Any]) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(cache, indent=2, sort_keys=True))


def round_coord(value: Any, precision: int) -> float | None:
    try:
        return round(float(value), precision)
    except Exception:
        return None


def safe_total(data: dict[str, Any], returned: int) -> int:
    for key in ["totalResults", "total", "resultCount"]:
        if key in data:
            try:
                return int(data[key])
            except Exception:
                pass
    return returned


def empty_result_row(ssid: str, mode: str, status: str, error: str = "", total: int = 0) -> dict[str, Any]:
    risk = score_ssid(ssid, total)
    return {
        "ssid": ssid,
        "wigle_total": total,
        "returned_index": 0,
        "lat_display": "",
        "lon_display": "",
        "city": "",
        "region": "",
        "country": "",
        "firsttime": "",
        "lasttime": "",
        "encryption": "",
        "risk_level": risk.level,
        "risk_score": risk.score,
        "risk_reason": risk.reason,
        "lookup_mode": mode,
        "lookup_status": status,
        "error": error,
        "looked_up_at": utc_now(),
    }


def rows_from_response(
    ssid: str,
    data: dict[str, Any],
    max_results_per_ssid: int,
    coord_precision: int,
    mode: str,
    status: str,
) -> list[dict[str, Any]]:
    results = data.get("results") or data.get("result") or []
    if not isinstance(results, list):
        results = []
    total = safe_total(data, len(results))
    risk = score_ssid(ssid, total)

    if not results:
        return [empty_result_row(ssid, mode, status=status, total=total)]

    rows: list[dict[str, Any]] = []
    for idx, item in enumerate(results[:max_results_per_ssid], start=1):
        if not isinstance(item, dict):
            continue
        lat = round_coord(item.get("trilat") or item.get("latitude"), coord_precision)
        lon = round_coord(item.get("trilong") or item.get("longitude"), coord_precision)
        rows.append({
            "ssid": ssid,
            "wigle_total": total,
            "returned_index": idx,
            "lat_display": lat if lat is not None else "",
            "lon_display": lon if lon is not None else "",
            "city": item.get("city", ""),
            "region": item.get("region", ""),
            "country": item.get("country", ""),
            "firsttime": item.get("firsttime", item.get("firstTime", "")),
            "lasttime": item.get("lasttime", item.get("lastupdt", item.get("lastUpdate", ""))),
            "encryption": item.get("encryption", ""),
            "risk_level": risk.level,
            "risk_score": risk.score,
            "risk_reason": risk.reason,
            "lookup_mode": mode,
            "lookup_status": status,
            "error": "",
            "looked_up_at": utc_now(),
        })
    return rows or [empty_result_row(ssid, mode, status=status, total=total)]


class WigleClient:
    def __init__(self, api_name: str, api_token: str, timeout: int = 30):
        self.api_name = api_name
        self.api_token = api_token
        self.timeout = timeout

    def search_ssid(self, ssid: str, max_results: int = 25, mode: str = "exact") -> dict[str, Any]:
        params: dict[str, Any] = {
            "onlymine": "false",
            "freenet": "false",
            "paynet": "false",
            "resultsPerPage": str(max_results),
        }
        if mode == "like":
            params["ssidlike"] = ssid
        else:
            params["ssid"] = ssid
        r = requests.get(
            API_URL,
            params=params,
            auth=(self.api_name, self.api_token),
            timeout=self.timeout,
            headers={"Accept": "application/json"},
        )
        if r.status_code == 429:
            raise RateLimitError("WiGLE rate limit hit: HTTP 429", retry_after=r.headers.get("Retry-After", ""))
        if r.status_code == 401:
            raise AuthenticationError("WiGLE authentication failed: HTTP 401")
        r.raise_for_status()
        return r.json()


def lookup_events(
    input_csv: str | Path,
    output_csv: str | Path,
    cache_path: str | Path,
    api_name: str,
    api_token: str,
    frame_type: str = "all",
    max_results_per_ssid: int = 10,
    sleep_seconds: float = 2.0,
    coord_precision: int = 3,
    mode: str = "exact",
    use_cache: bool = True,
    max_new_lookups: int = 10,
) -> pd.DataFrame:
    input_csv = Path(input_csv)
    output_csv = Path(output_csv)
    output_csv.parent.mkdir(parents=True, exist_ok=True)

    if not input_csv.exists():
        empty = pd.DataFrame(columns=OUTPUT_COLUMNS)
        empty.to_csv(output_csv, index=False)
        return empty

    events = pd.read_csv(input_csv, dtype=str).fillna("")
    if "ssid" not in events.columns:
        raise ValueError("Input CSV needs an ssid column")
    events["ssid"] = events["ssid"].map(clean_ssid)
    frame_type_normalized = (frame_type or "all").strip().lower()
    if frame_type_normalized not in {"", "all", "any", "*"} and "frame_type" in events.columns:
        events = events[events["frame_type"].eq(frame_type)].copy()

    ssids = sorted({s.strip() for s in events["ssid"].astype(str).tolist() if s.strip()})
    client = WigleClient(api_name, api_token)
    cache = load_cache(cache_path)
    rows: list[dict[str, Any]] = []
    new_lookup_count = 0
    rate_limited = False

    for ssid in ssids:
        cache_key = f"{mode}:{ssid}:max{max_results_per_ssid}"
        if use_cache and cache_key in cache:
            data = cache[cache_key].get("response", {})
            rows.extend(rows_from_response(ssid, data, max_results_per_ssid, coord_precision, mode, status="cache"))
            continue

        if rate_limited:
            rows.append(empty_result_row(ssid, mode, status="skipped_due_to_rate_limit", error="No API call made after HTTP 429 in this run"))
            continue

        if max_new_lookups >= 0 and new_lookup_count >= max_new_lookups:
            rows.append(empty_result_row(ssid, mode, status="skipped_max_new_lookups", error=f"Reached WIGLE_MAX_NEW_LOOKUPS_PER_RUN={max_new_lookups}"))
            continue

        try:
            data = client.search_ssid(ssid, max_results=max_results_per_ssid, mode=mode)
        except RateLimitError as exc:
            rate_limited = True
            rows.append(empty_result_row(ssid, mode, status="rate_limited", error=str(exc)))
            print(f"[!] {exc}. Partial results written; dashboard can continue.")
            continue
        except AuthenticationError:
            raise
        except requests.RequestException as exc:
            rows.append(empty_result_row(ssid, mode, status="request_error", error=str(exc)))
            print(f"[!] WiGLE request failed for SSID {ssid!r}: {exc}")
            continue

        new_lookup_count += 1
        cache[cache_key] = {"looked_up_at": utc_now(), "response": data}
        save_cache(cache_path, cache)
        rows.extend(rows_from_response(ssid, data, max_results_per_ssid, coord_precision, mode, status="api"))
        if sleep_seconds > 0:
            time.sleep(sleep_seconds)

    out = pd.DataFrame(rows, columns=OUTPUT_COLUMNS)
    out.to_csv(output_csv, index=False)
    if rate_limited:
        print("[!] WiGLE returned HTTP 429. The output contains partial/cache/skipped rows, not a complete lookup.")
    print(f"[+] WiGLE API calls made in this run: {new_lookup_count}")
    return out


def main(argv: list[str] | None = None) -> int:
    load_dotenv()
    ap = argparse.ArgumentParser(description="Enrich captured SSIDs with WiGLE location indicators.")
    ap.add_argument("--input", default=os.getenv("EVENTS_CSV", "data/input/ssid_events.csv"))
    ap.add_argument("--output", default=os.getenv("WIGLE_RESULTS_CSV", "data/results/wigle_results.csv"))
    ap.add_argument("--cache", default=os.getenv("WIGLE_CACHE", "data/cache/wigle_cache.json"))
    ap.add_argument("--frame-type", default=os.getenv("WIGLE_FRAME_TYPE", "all"))
    ap.add_argument("--max-results", type=int, default=int(os.getenv("WIGLE_MAX_RESULTS_PER_SSID", "10")))
    ap.add_argument("--sleep", type=float, default=float(os.getenv("WIGLE_SLEEP_SECONDS", "2.0")))
    ap.add_argument("--coord-precision", type=int, default=int(os.getenv("WIGLE_COORD_PRECISION", "3")))
    ap.add_argument("--mode", choices=["exact", "like"], default=os.getenv("WIGLE_LOOKUP_MODE", "exact"))
    ap.add_argument("--max-new-lookups", type=int, default=int(os.getenv("WIGLE_MAX_NEW_LOOKUPS_PER_RUN", "10")))
    ap.add_argument("--no-cache", action="store_true")
    args = ap.parse_args(argv)

    api_name = os.getenv("WIGLE_API_NAME", "").strip()
    api_token = os.getenv("WIGLE_API_TOKEN", "").strip()
    if not api_name or not api_token or api_name == "replace_me" or api_token == "replace_me":
        raise SystemExit("Missing WiGLE credentials. Set WIGLE_API_NAME and WIGLE_API_TOKEN in .env")

    lookup_events(
        args.input,
        args.output,
        args.cache,
        api_name=api_name,
        api_token=api_token,
        frame_type=args.frame_type,
        max_results_per_ssid=args.max_results,
        sleep_seconds=args.sleep,
        coord_precision=args.coord_precision,
        mode=args.mode,
        use_cache=not args.no_cache,
        max_new_lookups=args.max_new_lookups,
    )
    print(f"Wrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
