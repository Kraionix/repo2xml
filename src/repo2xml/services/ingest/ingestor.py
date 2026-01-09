from __future__ import annotations

import base64
import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Literal, Optional, Sequence

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
    ".png", ".jpg", ".jxl", ".jpeg", ".gif", ".bmp", ".ico", ".webp", ".tiff", ".tif",
    # Audio/Video
    ".mp3", ".wav", ".flac", ".ogg", ".m4a",
    ".mp4", ".mkv", ".avi", ".mov", ".webm",
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

    # Allow ASCII printable + whitespace; allow 0x80..0xFF (likely UTF-8 or legacy encodings).
    text_whitelist = set(b"\n\r\t\b\f") | set(range(0x20, 0x7F)) | set(range(0x80, 0x100))
    nontext = 0
    for b in sample:
        if b not in text_whitelist:
            nontext += 1

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


@dataclass(slots=True)
class IngestResult:
    """
    Output of StandardIngestor.ingest().

    - kind="text": decoded text available in `text`
    - kind="binary": binary detected
    - kind="skip": file intentionally skipped (size limit, etc.)
    - kind="error": failed to read/decode
    """
    kind: Literal["text", "binary", "skip", "error"]
    text: Optional[str] = None
    encoding: Optional[str] = None
    reason: Optional[str] = None


class StandardIngestor:
    """
    Read file content in a robust way.

    Design notes:
    - Uses size limit to avoid large reads.
    - Uses extension-based binary fast path (high confidence, configurable).
    - Uses BOM detection to decode UTF-16/32 correctly.
    - Supports newline normalization to reduce prompt noise.
    - Hash/base64 utilities are streaming and can be used by the pipeline when needed.
    """

    def __init__(
        self,
        *,
        max_size: int,
        newline_mode: str,  # "preserve" | "lf"
        use_ext_fastpath: bool = True,
        binary_ext_add: Optional[Sequence[str]] = None,
        binary_ext_remove: Optional[Sequence[str]] = None,
    ):
        self.max_size = max_size
        self.newline_mode = newline_mode
        self.use_ext_fastpath = use_ext_fastpath
        self.binary_ext_add = list(binary_ext_add) if binary_ext_add else []
        self.binary_ext_remove = list(binary_ext_remove) if binary_ext_remove else []

    def ingest(self, path: Path) -> IngestResult:
        # Stat first to enforce a hard size limit cheaply.
        try:
            st = path.stat()
        except OSError as e:
            return IngestResult(kind="error", reason=f"Error stat file: {e}")

        if st.st_size > self.max_size:
            return IngestResult(kind="skip", reason=f"Skipped: File size {st.st_size} exceeds limit {self.max_size}")

        # Fast-path binary classification by extension (no reads).
        if self.use_ext_fastpath and _is_likely_binary_by_extension(
            path, add=self.binary_ext_add, remove=self.binary_ext_remove
        ):
            return IngestResult(kind="binary")

        # Read a small sample for heuristics and BOM detection.
        try:
            with open(path, "rb") as f:
                sample = f.read(SNIFF_BYTES)

                bom_enc = _detect_bom(sample)
                if _looks_binary(sample, bom_enc):
                    return IngestResult(kind="binary")

                # Text path: we already have a size cap, so reading the rest is acceptable.
                rest = f.read()
        except OSError as e:
            return IngestResult(kind="error", reason=f"Error reading file: {e}")

        # Avoid `sample + rest` (extra large allocation/copy). Use a single growable buffer.
        buf = bytearray(sample)
        buf.extend(rest)

        enc = bom_enc or "utf-8"
        try:
            text = buf.decode(enc, errors="replace")
        except Exception as e:
            return IngestResult(kind="error", reason=f"Error decoding with {enc}: {e}")

        if self.newline_mode == "lf":
            # Normalize CRLF/CR to LF for more stable diffs and fewer prompt tokens.
            text = text.replace("\r\n", "\n").replace("\r", "\n")

        return IngestResult(kind="text", text=text, encoding=enc)

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