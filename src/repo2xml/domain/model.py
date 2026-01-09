from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Literal, Optional, Union


@dataclass(slots=True)
class FileEntry:
    """
    A single file discovered during scanning.

    - abs_path: absolute filesystem path used for reading
    - rel_path: repository-relative POSIX path used in output and filtering
    """
    abs_path: Path
    rel_path: str
    name: str
    size: int
    mtime_ns: int
    is_symlink: bool
    symlink_target: Optional[str] = None

    @property
    def ext(self) -> str:
        """Joined suffixes (e.g. '.tar.gz')."""
        return "".join(Path(self.rel_path).suffixes)


@dataclass(slots=True)
class ExportMeta:
    """Document-level metadata."""
    root_path: str
    generated_at_utc: Optional[str]
    tool_version: str
    schema_version: str = "1.0"


@dataclass(slots=True)
class ExportStats:
    """Execution statistics."""
    files_total: int
    files_emitted: int
    files_skipped: int
    files_errors: int
    scan_warning_summary: Optional[str] = None


@dataclass(slots=True)
class SniffResult:
    """
    Lightweight classification result for a file.

    This is intentionally small and cheap: it should not read full file content.
    """
    kind: Literal["text", "binary", "error"]
    encoding: Optional[str] = None
    reason: Optional[str] = None


@dataclass(slots=True)
class TextReadResult:
    """Result of a bounded text read."""
    kind: Literal["text", "skip", "error"]
    text: Optional[str] = None
    encoding: Optional[str] = None
    reason: Optional[str] = None


# Payloads represent how a file should be emitted by a serializer.
# This keeps serializers independent from scanning/ingestion policy switches.


@dataclass(slots=True)
class MetadataPayload:
    """
    Emit metadata only (no content).

    Semantics:
    - This is NOT an error and NOT "skipped".
    - Serializers should output a normal file entry without <content>.
    """


@dataclass(slots=True)
class LinkPayload:
    """
    Emit link metadata only (symlink-as-link mode).

    Semantics:
    - This is NOT an error and NOT "skipped".
    - Serializers should include link target info when available.
    """
    link_target: Optional[str] = None


@dataclass(slots=True)
class TextPayload:
    """Emit decoded text content."""
    text: str
    encoding: Optional[str] = None


@dataclass(slots=True)
class BinaryHashPayload:
    """Emit a hash summary for binary content."""
    sha256_hex: str


@dataclass(slots=True)
class BinaryBase64Payload:
    """
    Emit base64 for binary content.

    The payload contains an iterable of base64 chunks (ASCII strings).
    Serializers may stream them directly.
    """
    chunks: Iterable[str]


@dataclass(slots=True)
class SkippedPayload:
    """
    Emit a skipped marker with a human-readable reason.

    Semantics:
    - This is an intentional omission (size limits, binary skip mode, etc.).
    - Serializers should mark the entry as skipped.
    """
    reason: str


@dataclass(slots=True)
class ErrorPayload:
    """
    Emit an error marker with a human-readable message.

    Semantics:
    - This is a failed attempt to process a file (read/decode/hash errors, etc.).
    - Serializers should mark the entry as skipped/error.
    """
    message: str


FilePayload = Union[
    MetadataPayload,
    LinkPayload,
    TextPayload,
    BinaryHashPayload,
    BinaryBase64Payload,
    SkippedPayload,
    ErrorPayload,
]