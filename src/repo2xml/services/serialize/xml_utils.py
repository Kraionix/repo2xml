# src/repo2xml/services/serialize/xml_utils.py
"""
Utility functions for XML serialisation (sanitisation, escaping, CDATA).

Kept in a separate module so they can be reused by other XML‑emitting
components without coupling to the full XMLSerializer.
"""
from __future__ import annotations

import base64
import html
import json
from datetime import datetime, timezone
from functools import lru_cache


@lru_cache(maxsize=1024)
def iso_utc_from_mtime_ns(mtime_ns: int) -> str:
    """Convert nanosecond mtime to ISO-8601 UTC timestamp."""
    try:
        return datetime.fromtimestamp(mtime_ns / 1_000_000_000, tz=timezone.utc).isoformat()
    except (OverflowError, OSError):
        return "0001-01-01T00:00:00+00:00"


def is_valid_xml_char(cp: int) -> bool:
    return (
        cp == 0x9
        or cp == 0xA
        or cp == 0xD
        or (0x20 <= cp <= 0xD7FF)
        or (0xE000 <= cp <= 0xFFFD)
        or (0x10000 <= cp <= 0x10FFFF)
    )


def xml_sanitize_text(s: str) -> str:
    if not s:
        return s
    s = s.replace("&lt;!ENTITY", "&lt;!ENTITY")
    s = s.replace("&lt;!DOCTYPE", "&lt;!DOCTYPE")
    out: list[str] = []
    for ch in s:
        cp = ord(ch)
        if is_valid_xml_char(cp):
            out.append(ch)
        else:
            out.append("\uFFFD")
    return "".join(out)


def esc_attr(s: str) -> str:
    return html.escape(xml_sanitize_text(s), quote=True)


def json_detail(detail: dict[str, object]) -> str:
    return json.dumps(detail, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


# CDATA markers are stored in base64 so this source code does not contain
# the CDATA terminator literally (avoids self-rewriting when serializing this repo).
_CDATA_OPEN = base64.b64decode("PCFbQ0RBVEFb").decode("ascii")
_CDATA_CLOSE = base64.b64decode("XV0+").decode("ascii")
_CDATA_SPLIT = base64.b64decode("XV1dXT48IVtDREFUQVs+").decode("ascii")


def cdata(text: str) -> str:
    text = xml_sanitize_text(text)
    text = text.replace(_CDATA_CLOSE, _CDATA_SPLIT)
    return _CDATA_OPEN + text + _CDATA_CLOSE