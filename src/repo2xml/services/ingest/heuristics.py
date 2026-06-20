# src/repo2xml/services/ingest/heuristics.py
"""
Lightweight binary detection heuristics (BOM detection, null-byte check, ratio).

These functions are pure and intentionally kept outside any class to simplify
unit testing and future reuse (e.g., in a separate pre‑scan classifier).
"""
from __future__ import annotations

from typing import Optional

# Number of bytes used for binary/encoding heuristics.
SNIFF_BYTES = 4096

# BOM signatures (longest first). Used to detect UTF-8/16/32 text reliably.
_BOMS: list[tuple[bytes, str]] = [
    (b"\xff\xfe\x00\x00", "utf-32-le"),
    (b"\x00\x00\xfe\xff", "utf-32-be"),
    (b"\xef\xbb\xbf", "utf-8-sig"),
    (b"\xff\xfe", "utf-16-le"),
    (b"\xfe\xff", "utf-16-be"),
]

# Precomputed whitelist mask for the "looks binary" heuristic.
_TEXT_OK: bytearray = bytearray(256)
for _b in (0x09, 0x0A, 0x0D, 0x08, 0x0C):  # \t \n \r \b \f
    _TEXT_OK[_b] = 1
for _b in range(0x20, 0x7F):  # printable ASCII
    _TEXT_OK[_b] = 1
for _b in range(0x80, 0x100):  # high bytes (UTF-8 continuation / legacy encodings)
    _TEXT_OK[_b] = 1
del _b


def detect_bom(data: bytes) -> Optional[str]:
    """Return encoding name if the data starts with a known BOM."""
    for bom, enc in _BOMS:
        if data.startswith(bom):
            return enc
    return None


def looks_binary(sample: bytes, bom_encoding: Optional[str]) -> bool:
    """
    Heuristic binary detection.

    Rules:
    - If UTF-16/32 BOM is present, treat it as text (do not reject due to null bytes).
    - If there is a null byte and no UTF-16/32 BOM, it is likely binary.
    - Otherwise estimate the ratio of non-text bytes.
    """
    if not sample:
        return False
    if bom_encoding and (bom_encoding.startswith("utf-16") or bom_encoding.startswith("utf-32")):
        return False
    if b"\x00" in sample:
        return True
    nontext = sum(1 for b in sample if not _TEXT_OK[b])
    return (nontext / len(sample)) > 0.30