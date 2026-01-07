from __future__ import annotations

import base64
import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Optional

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

    This is intentionally pragmatic: for LLM context generation, it is better
    to avoid embedding large binary blobs by accident.
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


@dataclass(slots=True)
class IngestResult:
    """
    Output of FileIngestor.read().

    - kind="text": decoded text available in `text`
    - kind="binary": raw bytes available in `binary_bytes`
    - kind="skip": file intentionally skipped (size limit, etc.)
    - kind="error": failed to read/decode
    """
    kind: Literal["text", "binary", "skip", "error"]
    text: Optional[str] = None
    binary_bytes: Optional[bytes] = None
    error: Optional[str] = None
    encoding: Optional[str] = None


class FileIngestor:
    """
    Read file content in a robust way.

    Design notes:
    - Reads bytes once (single pass).
    - Uses BOM detection to decode UTF-16/32 correctly.
    - Supports newline normalization to reduce prompt noise.
    """

    @staticmethod
    def read(
        path: Path,
        *,
        max_size: int,
        newline_mode: str,  # "preserve" | "lf"
    ) -> IngestResult:
        # Stat first to enforce a hard size limit cheaply.
        try:
            st = path.stat()
        except OSError as e:
            return IngestResult(kind="error", error=f"Error stat file: {e}")

        if st.st_size > max_size:
            return IngestResult(kind="skip", error=f"Skipped: File size {st.st_size} exceeds limit {max_size}")

        # Read bytes once.
        try:
            raw = path.read_bytes()
        except OSError as e:
            return IngestResult(kind="error", error=f"Error reading file: {e}")

        sample = raw[:SNIFF_BYTES]
        bom_enc = _detect_bom(sample)

        if _looks_binary(sample, bom_enc):
            return IngestResult(kind="binary", binary_bytes=raw)

        enc = bom_enc or "utf-8"
        try:
            text = raw.decode(enc, errors="replace")
        except Exception as e:
            return IngestResult(kind="error", error=f"Error decoding with {enc}: {e}")

        if newline_mode == "lf":
            # Normalize CRLF/CR to LF for more stable diffs and fewer prompt tokens.
            text = text.replace("\r\n", "\n").replace("\r", "\n")

        return IngestResult(kind="text", text=text, encoding=enc)

    @staticmethod
    def to_base64(data: bytes) -> str:
        """Encode bytes to base64 ASCII string for embedding in XML."""
        return base64.b64encode(data).decode("ascii")

    @staticmethod
    def sha256_hex(data: bytes) -> str:
        """Compute SHA-256 hex digest for binary content summarization."""
        return hashlib.sha256(data).hexdigest()