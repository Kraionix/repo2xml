# src/repo2xml/services/ingest/matcher.py
"""
Precomputed binary extension matcher (simple + compound suffixes).

Kept as a separate module to isolate the default extension sets and the
matcher logic from the ingestor implementation.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Sequence


# High-confidence binary extensions for quick classification.
_BINARY_EXTS: set[str] = {
    # Images
    ".png", ".jpg", ".jxl", ".jpeg", ".gif", ".bmp", ".ico", ".webp", ".tiff", ".tif",
    # Audio/Video
    ".mp3", ".wav", ".flac", ".ogg", ".m4a", ".mp4", ".mkv", ".avi", ".mov", ".webm",
    # Archives / compressed
    ".zip", ".gz", ".bz2", ".xz", ".7z", ".rar",
    # Documents
    ".pdf",
    # Fonts
    ".ttf", ".otf", ".woff", ".woff2",
    # Executables / libs
    ".exe", ".dll", ".so", ".dylib",
    # Bytecode / data
    ".pyc", ".pyo", ".class",
    # Misc
    ".bin", ".dat",
}

# Common compound suffixes (Path.suffix only returns last part).
_BINARY_COMPOUND_SUFFIXES: set[str] = {
    ".tar.gz", ".tar.bz2", ".tar.xz",
}


def _norm_ext(s: str) -> str:
    """Normalize an extension string for matching."""
    t = s.strip().lower()
    if not t:
        return ""
    if not t.startswith("."):
        t = "." + t
    return t


def _build_binary_ext_sets(
    *,
    add: Optional[Sequence[str]],
    remove: Optional[Sequence[str]],
) -> tuple[set[str], set[str]]:
    """Build binary extension sets with optional user overrides."""
    exts = set(_BINARY_EXTS)
    comps = set(_BINARY_COMPOUND_SUFFIXES)

    def apply_remove(v: str) -> None:
        if v.count(".") >= 2:
            comps.discard(v)
        exts.discard(v)

    def apply_add(v: str) -> None:
        if v.count(".") >= 2:
            comps.add(v)
        else:
            exts.add(v)

    if remove:
        for raw in remove:
            v = _norm_ext(raw)
            if v:
                apply_remove(v)
    if add:
        for raw in add:
            v = _norm_ext(raw)
            if v:
                apply_add(v)
    return exts, comps


@dataclass(slots=True, frozen=True)
class BinaryExtensionMatcher:
    """Precomputed binary extension matcher (simple + compound suffixes)."""
    simple_exts: frozenset[str]
    compound_suffixes: frozenset[str]

    @classmethod
    def create(
        cls,
        *,
        add: Optional[Sequence[str]] = None,
        remove: Optional[Sequence[str]] = None,
    ) -> "BinaryExtensionMatcher":
        exts, comps = _build_binary_ext_sets(add=add, remove=remove)
        return cls(simple_exts=frozenset(exts), compound_suffixes=frozenset(comps))

    def matches(self, path: Path) -> bool:
        suffixes = [s.lower() for s in path.suffixes]
        if not suffixes:
            return False
        if len(suffixes) >= 2:
            comp = "".join(suffixes[-2:])
            if comp in self.compound_suffixes:
                return True
        return suffixes[-1] in self.simple_exts