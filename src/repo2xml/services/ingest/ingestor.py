from __future__ import annotations

import base64
import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional, Sequence

from repo2xml.domain.model import ErrorCode, ErrorInfo, SkipCode, SkipInfo, SniffResult, TextReadResult

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

# High-confidence binary extensions for quick classification.
_BINARY_EXTS: set[str] = {
    # Images
    ".png",
    ".jpg",
    ".jxl",
    ".jpeg",
    ".gif",
    ".bmp",
    ".ico",
    ".webp",
    ".tiff",
    ".tif",
    # Audio/Video
    ".mp3",
    ".wav",
    ".flac",
    ".ogg",
    ".m4a",
    ".mp4",
    ".mkv",
    ".avi",
    ".mov",
    ".webm",
    # Archives / compressed
    ".zip",
    ".gz",
    ".bz2",
    ".xz",
    ".7z",
    ".rar",
    # Documents
    ".pdf",
    # Fonts
    ".ttf",
    ".otf",
    ".woff",
    ".woff2",
    # Executables / libs
    ".exe",
    ".dll",
    ".so",
    ".dylib",
    # Bytecode / data
    ".pyc",
    ".pyo",
    ".class",
    # Misc
    ".bin",
    ".dat",
}

# Common compound suffixes (Path.suffix only returns last part).
_BINARY_COMPOUND_SUFFIXES: set[str] = {
    ".tar.gz",
    ".tar.bz2",
    ".tar.xz",
}

# Precomputed whitelist mask for the "looks binary" heuristic.
# Using a bytearray mask avoids per-call set construction and speeds membership checks.
_TEXT_OK: bytearray = bytearray(256)
for _b in (0x09, 0x0A, 0x0D, 0x08, 0x0C):  # \t \n \r \b \f
    _TEXT_OK[_b] = 1
for _b in range(0x20, 0x7F):  # printable ASCII
    _TEXT_OK[_b] = 1
for _b in range(0x80, 0x100):  # high bytes (UTF-8 continuation / legacy encodings)
    _TEXT_OK[_b] = 1
del _b


def _detect_bom(data: bytes) -> Optional[str]:
    """Return encoding name if the data starts with a known BOM."""
    for bom, enc in _BOMS:
        if data.startswith(bom):
            return enc
    return None


def _looks_binary(sample: bytes, bom_encoding: Optional[str]) -> bool:
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


def _norm_ext(s: str) -> str:
    """
    Normalize an extension string for matching.

    - Case-insensitive: always lowercased.
    - Adds a leading dot if missing ("PNG" -> ".png").
    """
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
    """
    Build binary extension sets with optional user overrides.
    """
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


def _is_likely_binary_by_extension(
    path: Path,
    *,
    add: Optional[Sequence[str]] = None,
    remove: Optional[Sequence[str]] = None,
) -> bool:
    """
    Fast-path: classify obvious binary formats by filename extension.
    Matching is case-insensitive.

    Note: StandardIngestor uses a cached matcher for performance. This helper
    remains for direct unit testing and standalone use.
    """
    suffixes = [s.lower() for s in path.suffixes]
    if not suffixes:
        return False

    exts, comps = _build_binary_ext_sets(add=add, remove=remove)

    # Compound suffix match (".tar.gz" etc).
    if len(suffixes) >= 2:
        comp = "".join(suffixes[-2:])
        if comp in comps:
            return True

    return suffixes[-1] in exts


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


class StandardIngestor:
    """
    Ingestor responsible for safe reading and lightweight classification.

    Design notes:
    - sniff(): low-cost classification (binary vs text) using extension fast-path and a small sample.
    - read_text(): bounded read of a text file with size limits and newline normalization.
    - Hash/base64 utilities are streaming and can be used by the pipeline when needed.
    """

    def __init__(
        self,
        *,
        newline_mode: str,  # "preserve" | "lf"
        use_ext_fastpath: bool = True,
        binary_ext_add: Optional[Sequence[str]] = None,
        binary_ext_remove: Optional[Sequence[str]] = None,
    ):
        self.newline_mode = newline_mode
        self.use_ext_fastpath = use_ext_fastpath
        self.binary_ext_add = list(binary_ext_add) if binary_ext_add else []
        self.binary_ext_remove = list(binary_ext_remove) if binary_ext_remove else []

        # Cache extension matcher once per ingestor instance.
        self._ext_matcher: Optional[BinaryExtensionMatcher] = None
        if self.use_ext_fastpath:
            self._ext_matcher = BinaryExtensionMatcher.create(
                add=self.binary_ext_add,
                remove=self.binary_ext_remove,
            )

    def sniff(self, path: Path) -> SniffResult:
        """
        Classify a file as likely text or binary using minimal IO.

        This method does not enforce size limits and does not read full content.
        """
        # Fast-path binary classification by extension (no reads).
        if self._ext_matcher is not None and self._ext_matcher.matches(path):
            return SniffResult(kind="binary")

        # Read a small sample for heuristics and BOM detection.
        try:
            with open(path, "rb") as f:
                sample = f.read(SNIFF_BYTES)
        except OSError as e:
            err = ErrorInfo(code=ErrorCode.sniff_read_error, detail={"os_error": str(e)})
            return SniffResult(kind="error", error=err)

        bom_enc = _detect_bom(sample)
        if _looks_binary(sample, bom_enc):
            return SniffResult(kind="binary", encoding=bom_enc)

        return SniffResult(kind="text", encoding=bom_enc or "utf-8")

    def read_text(self, path: Path, *, max_size: int) -> TextReadResult:
        """
        Read and decode a file as text, enforcing a hard size limit.

        Even if the caller already used sniff(), we still guard against accidentally
        embedding binary-like content by re-checking the initial sample.
        """
        try:
            st = path.stat()
        except OSError as e:
            err = ErrorInfo(code=ErrorCode.stat_error, detail={"os_error": str(e)})
            return TextReadResult(kind="error", error=err)

        if st.st_size > max_size:
            info = SkipInfo(code=SkipCode.text_size_limit, detail={"size": st.st_size, "limit": max_size})
            return TextReadResult(kind="skip", skipped=info)

        try:
            with open(path, "rb") as f:
                sample = f.read(SNIFF_BYTES)
                bom_enc = _detect_bom(sample)

                # Safety check: avoid embedding binary even if caller classified it incorrectly.
                if _looks_binary(sample, bom_enc):
                    err = ErrorInfo(code=ErrorCode.binary_detected, detail={})
                    return TextReadResult(kind="error", error=err)

                rest = f.read()
        except OSError as e:
            err = ErrorInfo(code=ErrorCode.text_read_error, detail={"os_error": str(e)})
            return TextReadResult(kind="error", error=err)

        buf = bytearray(sample)
        buf.extend(rest)

        enc = bom_enc or "utf-8"
        try:
            text = buf.decode(enc, errors="replace")
        except Exception as e:
            err = ErrorInfo(code=ErrorCode.text_decode_error, detail={"encoding": enc, "decode_error": str(e)})
            return TextReadResult(kind="error", error=err)

        if self.newline_mode == "lf":
            # Normalize CRLF/CR to LF for more stable diffs and fewer prompt tokens.
            text = text.replace("\r\n", "\n").replace("\r", "\n")

        return TextReadResult(kind="text", text=text, encoding=enc)

    @staticmethod
    def sha256_file(path: Path, *, chunk_size: int = 1024 * 64) -> str:
        """Compute SHA-256 hex digest for a file in a streaming fashion."""
        h = hashlib.sha256()
        with open(path, "rb") as f:
            while True:
                chunk = f.read(chunk_size)
                if not chunk:
                    break
                h.update(chunk)
        return h.hexdigest()

    @staticmethod
    def iter_base64_chunks(path: Path, *, chunk_size: int = 1024 * 64) -> Iterable[str]:
        """
        Yield base64 ASCII chunks for a file, streaming.

        We keep the chunk boundary aligned to 3 bytes (base64 quantum) to avoid
        inserting padding in the middle.
        """
        rem = b""
        with open(path, "rb") as f:
            while True:
                chunk = f.read(chunk_size)
                if not chunk:
                    break

                data = rem + chunk
                n = (len(data) // 3) * 3
                block = data[:n]
                rem = data[n:]

                if block:
                    yield base64.b64encode(block).decode("ascii")

        if rem:
            yield base64.b64encode(rem).decode("ascii")