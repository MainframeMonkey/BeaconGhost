from __future__ import annotations

import re
import unicodedata
from typing import Any

BAD_SSIDS = {
    "", "<missing>", "<hidden>", "hidden", "broadcast", "wildcard",
    "ssid parameter set: wildcard ssid", "\\x00", "\\000", "null", "none",
    "wildcard ssid", "broadcast ssid", "ssid=", "ssid:", "ssid=null",
}

HEX_PAIR_RE = re.compile(r"^(?:0x)?(?:[0-9A-Fa-f]{2}[:\-\s]?)+$")
CONTIG_HEX_RE = re.compile(r"^(?:0x)?[0-9A-Fa-f]+$")
ESCAPED_HEX_RE = re.compile(r"(?:\\\\x|\\x)([0-9A-Fa-f]{2})")
ESCAPED_OCTAL_RE = re.compile(r"(?:\\\\|\\)([0-7]{3})")
URL_HEX_RE = re.compile(r"(?:%[0-9A-Fa-f]{2})+")
INFO_SSID_RE = re.compile(r"SSID\s*[=:]\s*", re.IGNORECASE)


def _strip_outer(value: str) -> str:
    s = value.strip()
    while len(s) >= 2 and ((s[0] == s[-1] == '"') or (s[0] == s[-1] == "'")):
        s = s[1:-1].strip()
    return s


def _printable_ratio(text: str) -> float:
    if not text:
        return 0.0
    good = 0
    total = 0
    for ch in text:
        total += 1
        if ch in "\t\n\r":
            continue
        o = ord(ch)
        if o >= 0x20 and o != 0x7f:
            good += 1
    return good / max(total, 1)


def _text_quality(text: str) -> float:
    if not text:
        return 0.0
    good = 0
    for ch in text:
        cat = unicodedata.category(ch)
        if cat[0] in {"L", "N", "P", "S", "Z"} and cat not in {"Cf", "Cc", "Cs"}:
            good += 1
    return good / max(len(text), 1)


def _looks_like_text(text: str) -> bool:
    if not text or "\ufffd" in text:
        return False
    if _printable_ratio(text) < 0.90:
        return False
    if _text_quality(text) < 0.85:
        return False
    # Avoid decoding arbitrary byte blobs such as deadbeef into mojibake.
    common = sum(1 for ch in text if ch.isalnum() or ch in " _.-:#/+()[]{}@!$%&=,'`~")
    if common / max(len(text), 1) < 0.50:
        return False
    return True


def _decode_bytes_best_effort(raw: bytes) -> str:
    raw = raw.replace(b"\x00", b"")
    if not raw:
        return ""

    # SSIDs are byte strings; for normal human SSIDs, UTF-8 or ASCII succeeds.
    for enc in ("utf-8", "cp1252", "latin-1"):
        try:
            text = raw.decode(enc, errors="strict")
        except Exception:
            continue
        text = text.replace("\x00", "").strip()
        if _looks_like_text(text):
            return text
    return ""


def _decode_hex_string(value: str) -> str:
    s = _strip_outer(value)
    if not s:
        return ""

    if s.lower().startswith("0x"):
        s_no_prefix = s[2:]
    else:
        s_no_prefix = s

    # Escaped hex bytes: \x4d\x79 or \\x4d\\x79.
    escaped = ESCAPED_HEX_RE.findall(s)
    if escaped:
        return _decode_bytes_best_effort(bytes(int(x, 16) for x in escaped))

    # Escaped octal bytes: \115\171.
    octal = ESCAPED_OCTAL_RE.findall(s)
    if octal and len(octal) * 4 >= len(s.replace("\\\\", "\\")) - 1:
        return _decode_bytes_best_effort(bytes(int(x, 8) for x in octal))

    # URL-style hex bytes: %4d%79.
    if URL_HEX_RE.fullmatch(s):
        try:
            return _decode_bytes_best_effort(bytes(int(part, 16) for part in re.findall(r"%([0-9A-Fa-f]{2})", s)))
        except Exception:
            return ""

    # Colon/dash/space separated bytes: 4d:79:48:6f or 4d 79 48 6f.
    if HEX_PAIR_RE.fullmatch(s) and re.search(r"[:\-\s]", s):
        hexstr = re.sub(r"[^0-9A-Fa-f]", "", s_no_prefix)
        if not hexstr or set(hexstr) == {"0"}:
            return ""
        if len(hexstr) % 2 == 0:
            try:
                return _decode_bytes_best_effort(bytes.fromhex(hexstr))
            except ValueError:
                return ""

    # Continuous bytes: 4879647261 -> Hydra.
    if CONTIG_HEX_RE.fullmatch(s) and len(s_no_prefix) >= 4 and len(s_no_prefix) % 2 == 0:
        if set(s_no_prefix) == {"0"}:
            return ""
        try:
            return _decode_bytes_best_effort(bytes.fromhex(s_no_prefix))
        except ValueError:
            return ""

    return ""


def ssid_from_info_column(value: Any) -> str:
    """Extract SSID text from TShark's _ws.col.Info fallback column."""
    if value is None:
        return ""
    info = str(value).strip()
    if not info:
        return ""

    match = None
    for match in INFO_SSID_RE.finditer(info):
        pass
    if match is None:
        return ""

    tail = info[match.end():].strip()
    if not tail:
        return ""

    if tail[0] in {'"', "'"}:
        quote = tail[0]
        end = tail.find(quote, 1)
        if end > 0:
            return clean_ssid(tail[1:end])
        return clean_ssid(tail[1:])

    # Info usually ends with SSID=<name>. If more fields follow, stop at the next
    # comma-space token. SSIDs containing commas are still handled by wlan.ssid.
    tail = re.split(r",\s+(?:DS|SAE|HT|VHT|HE|RSN|Supported|Extended|Rates|Channel|SN=|FN=|Flags=)", tail, maxsplit=1)[0]
    return clean_ssid(tail.strip())


def clean_ssid(value: Any) -> str:
    if value is None:
        return ""
    s = str(value).strip()
    if not s:
        return ""

    s = s.replace("\\000", "").replace("\x00", "").strip()
    s = re.sub(r"[\x00-\x1f\x7f]", "", s).strip()
    s = _strip_outer(s)

    lowered = s.lower().strip()
    for marker in ("ssid parameter set: ssid:", "ssid parameter set:", "ssid:", "ssid="):
        if lowered.startswith(marker):
            s = s[len(marker):].strip()
            lowered = s.lower().strip()
            break

    decoded = _decode_hex_string(s)
    if decoded:
        s = decoded

    s = re.sub(r"[\x00-\x1f\x7f]", "", s).strip()
    s = _strip_outer(s)
    normalized = re.sub(r"\s+", " ", s).strip().lower()

    if normalized in BAD_SSIDS:
        return ""
    if normalized.startswith("tag length") or normalized.startswith("tag number"):
        return ""
    # Single/two-digit field artefacts are usually length or tag IDs, not useful
    # SSID names for this workflow. Longer numeric names are kept.
    if re.fullmatch(r"\d{1,2}", normalized):
        return ""
    if len(s.encode("utf-8", errors="ignore")) > 64:
        return ""
    return s


def best_ssid(*values: Any) -> str:
    """Return the best readable SSID from raw field and Info-column candidates."""
    candidates: list[str] = []
    for value in values:
        if value is None:
            continue
        raw = str(value).strip()
        if not raw:
            continue
        from_info = ssid_from_info_column(raw)
        if from_info:
            candidates.append(from_info)
            continue
        cleaned = clean_ssid(raw)
        if cleaned:
            candidates.append(cleaned)

    if not candidates:
        return ""

    # Prefer candidates with visible letters/spaces/punctuation over byte-looking
    # leftovers. Numeric SSIDs are valid, but less informative when alternatives
    # exist from the Info column.
    def rank(text: str) -> tuple[int, int, int]:
        letters = sum(ch.isalpha() for ch in text)
        common = sum(1 for ch in text if ch.isalnum() or ch in " _.-:#/+()[]{}@!$%&=,'`~")
        numeric_only = 1 if text.isdigit() else 0
        return (0 if numeric_only else 1, letters, common)

    return sorted(dict.fromkeys(candidates), key=rank, reverse=True)[0]


def normalize_ssid_series(values: list[Any]) -> list[str]:
    return [clean_ssid(v) for v in values]
