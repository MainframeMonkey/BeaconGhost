from __future__ import annotations

import re
from dataclasses import dataclass

GENERIC_EXACT = {
    "wifi", "wi-fi", "wlan", "guest", "guest wifi", "guest-wifi", "free wifi",
    "freewifi", "hotspot", "internet", "public", "default", "linksys",
    "netgear", "tplink", "tp-link", "dlink", "eduroam", "swisscom", "sunrise",
    "salt", "fritz!box", "vodafone", "telekom", "orange", "hotel", "airport",
    "cafe", "restaurant", "printer", "hp-print", "direct", "androidap",
}

GENERIC_PATTERNS = [
    r"^guest[-_ ]?\d*$",
    r"^wifi[-_ ]?\d*$",
    r"^wlan[-_ ]?\d*$",
    r"^fritz!box[\w -]*$",
    r"^hp[-_ ]?print[\w -]*$",
    r"^direct[-_ ].*$",
    r"^chromecast[\w -]*$",
    r"^hotel[-_ ]?wifi$",
]

@dataclass(frozen=True)
class RiskResult:
    level: str
    score: int
    reason: str


def is_generic_ssid(ssid: str) -> bool:
    s = (ssid or "").strip().lower()
    if not s:
        return True
    if s in GENERIC_EXACT:
        return True
    for pattern in GENERIC_PATTERNS:
        if re.match(pattern, s):
            return True
    return False


def score_ssid(ssid: str, wigle_total: int | None) -> RiskResult:
    ssid = ssid or ""
    total = 0 if wigle_total is None else int(wigle_total)
    generic = is_generic_ssid(ssid)

    if total <= 0:
        return RiskResult("none", 0, "No WiGLE matches returned")

    if len(ssid.strip()) < 4:
        return RiskResult("low", 10, "Very short SSID; weak signal")

    if generic:
        if total <= 3:
            return RiskResult("medium", 45, "Generic-looking SSID but rare in returned results")
        return RiskResult("low", 20, "Generic or common SSID")

    if total <= 3:
        return RiskResult("high", 85, "Rare SSID in WiGLE results")
    if total <= 10:
        return RiskResult("medium", 65, "Limited WiGLE matches; possible location indicator")
    if total <= 25:
        return RiskResult("medium", 50, "Moderate number of matches; ambiguous indicator")
    return RiskResult("low", 25, "Many WiGLE matches; likely ambiguous")
