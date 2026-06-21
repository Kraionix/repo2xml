# src/repo2xml/services/classify/classifiers.py
"""Fast-path classifiers based on file extensions and content heuristics."""
from __future__ import annotations

from pathlib import Path
from typing import FrozenSet, Optional


class ExtensionClassifier:
    """Classify files by extension using precompiled whitelists/blacklists."""

    def __init__(
        self,
        text_exts: FrozenSet[str],
        binary_exts: FrozenSet[str],
        compound_binary_suffixes: FrozenSet[str],
    ):
        self._text_exts = text_exts
        self._binary_exts = binary_exts
        self._compound_suffixes = compound_binary_suffixes

    def classify(self, path: Path) -> Optional[str]:
        """Return 'text', 'binary', or None if extension is not decisive."""
        suffixes = [s.lower() for s in path.suffixes]
        if not suffixes:
            return None

        # Check binary compounds first (e.g., .tar.gz)
        if len(suffixes) >= 2:
            comp = "".join(suffixes[-2:])
            if comp in self._compound_suffixes:
                return "binary"

        last = suffixes[-1]
        if last in self._binary_exts:
            return "binary"
        if last in self._text_exts:
            return "text"
        return None


# ----------------------------------------------------------------------
# Content heuristic (BOM + null‑byte ratio)
# ----------------------------------------------------------------------

SNIFF_BYTES = 4096

_BOMS: list[tuple[bytes, str]] = [
    (b"\xff\xfe\x00\x00", "utf-32-le"),
    (b"\x00\x00\xfe\xff", "utf-32-be"),
    (b"\xef\xbb\xbf", "utf-8-sig"),
    (b"\xff\xfe", "utf-16-le"),
    (b"\xfe\xff", "utf-16-be"),
]

_TEXT_OK: bytearray = bytearray(256)
for _b in (0x09, 0x0A, 0x0D, 0x08, 0x0C):
    _TEXT_OK[_b] = 1
for _b in range(0x20, 0x7F):
    _TEXT_OK[_b] = 1
for _b in range(0x80, 0x100):
    _TEXT_OK[_b] = 1


def detect_bom(data: bytes) -> Optional[str]:
    """Return encoding name if the data starts with a known BOM."""
    for bom, enc in _BOMS:
        if data.startswith(bom):
            return enc
    return None


def looks_binary(sample: bytes, bom_encoding: Optional[str], threshold: float = 0.30) -> bool:
    if not sample:
        return False
    if bom_encoding and (bom_encoding.startswith("utf-16") or bom_encoding.startswith("utf-32")):
        return False
    if b"\x00" in sample:
        return True
    nontext = sum(1 for b in sample if not _TEXT_OK[b])
    return (nontext / len(sample)) > threshold