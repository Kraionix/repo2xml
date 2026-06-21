# src/repo2xml/domain/model.py
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Iterable, Iterator, List, Literal, Optional, Union, Any


@dataclass(slots=True)
class FileEntry:
    """A single file discovered during scanning or described in a parsed document."""
    abs_path: Path
    rel_path: str          # repository-relative POSIX path
    name: str
    size: int
    mtime_ns: int
    is_symlink: bool
    symlink_target: Optional[str] = None

    @property
    def ext(self) -> str:
        return "".join(Path(self.name).suffixes)


@dataclass(slots=True)
class ExportMeta:
    """Document-level metadata emitted by an export."""
    root_path: str
    generated_at_utc: Optional[str]
    tool_version: str
    schema_version: str


@dataclass(slots=True)
class RestoreMeta:
    """Metadata about a restore operation."""
    target_root: str               # absolute path where the repository is restored
    restored_at_utc: str           # ISO-8601 timestamp of the restore
    source_document: Optional[str] # optional identifier of the source XML


class SkipCode(str, Enum):
    binary_skip_mode = "binary_skip_mode"
    text_size_limit = "text_size_limit"
    base64_size_limit = "base64_size_limit"
    hash_size_limit = "hash_size_limit"
    unknown = "unknown"


class ErrorCode(str, Enum):
    sniff_read_error = "sniff_read_error"
    stat_error = "stat_error"
    text_read_error = "text_read_error"
    text_decode_error = "text_decode_error"
    binary_detected = "binary_detected"
    binary_hash_error = "binary_hash_error"
    base64_error = "base64_error"
    processor_error = "processor_error"
    unknown = "unknown"


@dataclass(slots=True)
class SkipInfo:
    code: SkipCode
    detail: dict[str, object] = field(default_factory=dict)


@dataclass(slots=True)
class ErrorInfo:
    code: ErrorCode
    detail: dict[str, object] = field(default_factory=dict)


@dataclass(slots=True)
class ExportStats:
    files_total: int
    files_emitted: int
    files_skipped: int
    files_errors: int
    skipped_by_code: dict[str, int] = field(default_factory=dict)
    errors_by_code: dict[str, int] = field(default_factory=dict)
    scan_warning_summary: Optional[str] = None
    # New field for redaction statistics (avoid heavy coupling with services)
    redaction_stats: Optional[Any] = None


@dataclass(slots=True)
class RestoreStats:
    files_total: int
    files_created: int
    files_skipped: int
    files_errors: int
    dirs_created: int
    symlinks_created: int
    skipped_by_code: dict[str, int] = field(default_factory=dict)
    errors_by_code: dict[str, int] = field(default_factory=dict)


@dataclass(slots=True)
class SniffResult:
    kind: Literal["text", "binary", "error"]
    encoding: Optional[str] = None
    error: Optional[ErrorInfo] = None


@dataclass(slots=True)
class TextReadResult:
    kind: Literal["text", "skip", "error"]
    text: Optional[str] = None
    encoding: Optional[str] = None
    skipped: Optional[SkipInfo] = None
    error: Optional[ErrorInfo] = None


# ---- Payload hierarchy (sealed) ----

@dataclass(slots=True)
class MetadataPayload:
    """File entry with metadata only, no content."""


@dataclass(slots=True)
class LinkPayload:
    """Symlink entry."""
    link_target: Optional[str] = None


@dataclass(slots=True)
class TextPayload:
    """Decoded text content."""
    text: str
    encoding: Optional[str] = None


@dataclass(slots=True)
class BinaryHashPayload:
    """Hash of binary content; original bytes not available."""
    sha256_hex: str


@dataclass(slots=True)
class BinaryBase64Payload:
    """Binary content encoded as an iterable of base64 chunks (ASCII strings)."""
    chunks: Iterable[str]


@dataclass(slots=True)
class SkippedPayload:
    """Intentionally omitted file (e.g., size limit)."""
    code: SkipCode
    message: str
    detail: dict[str, object] = field(default_factory=dict)


@dataclass(slots=True)
class ErrorPayload:
    """Processing error."""
    code: ErrorCode
    message: str
    detail: dict[str, object] = field(default_factory=dict)


FilePayload = Union[
    MetadataPayload,
    LinkPayload,
    TextPayload,
    BinaryHashPayload,
    BinaryBase64Payload,
    SkippedPayload,
    ErrorPayload,
]


# ---- Restore-specific structures ----

@dataclass(slots=True)
class RestoreEntry:
    """Pair of file metadata and its payload to be restored."""
    entry: FileEntry
    payload: FilePayload


@dataclass(slots=True)
class ParsedRepository:
    """Result of deserialising an export document."""
    meta: ExportMeta
    structure: List[FileEntry]      # ordered tree as in <project_structure>
    files: Iterator[RestoreEntry]   # lazy stream of file payloads