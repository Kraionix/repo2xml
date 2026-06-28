# src/repo2xml/domain/model.py
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, Iterable, Iterator, List, Literal, Optional, Union

if TYPE_CHECKING:
    from repo2xml.services.scan.scanner import ScanStats


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
    token_count: Optional[int] = None   # number of tokens (only for text files, optional)

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
    target_root: str
    restored_at_utc: str
    source_document: Optional[str]


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
class TokenStats:
    """Aggregated token counting statistics."""
    total_tokens: int = 0
    files_processed: int = 0
    files_skipped: int = 0
    tokens_by_extension: Dict[str, int] = field(default_factory=dict)
    max_tokens: int = 0
    min_tokens: int = 0
    errors: int = 0


@dataclass(slots=True)
class ExportStats:
    files_total: int
    files_emitted: int
    files_skipped: int
    files_errors: int
    skipped_by_code: dict[str, int] = field(default_factory=dict)
    errors_by_code: dict[str, int] = field(default_factory=dict)
    scan_warning_summary: Optional[str] = None
    redaction_stats: Optional[Any] = None
    classification_stats: Optional[Any] = None
    token_stats: Optional[TokenStats] = None
    scan_stats: Optional["ScanStats"] = None   # Detailed scan error statistics


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
class ClassificationResult:
    kind: Literal["text", "binary", "error"]
    encoding: Optional[str] = None
    sample: Optional[bytes] = None
    error: Optional[str] = None


@dataclass(slots=True)
class TextReadResult:
    kind: Literal["text", "skip", "error"]
    text: Optional[str] = None
    encoding: Optional[str] = None
    skipped: Optional[SkipInfo] = None
    error: Optional[ErrorInfo] = None


# ---- Payload hierarchy ----

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
    """Hash of binary content."""
    sha256_hex: str


@dataclass(slots=True)
class BinaryBase64Payload:
    """Binary content encoded as base64 chunks."""
    chunks: Iterable[str]


@dataclass(slots=True)
class SkippedPayload:
    code: SkipCode
    message: str
    detail: dict[str, object] = field(default_factory=dict)


@dataclass(slots=True)
class ErrorPayload:
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
    entry: FileEntry
    payload: FilePayload


@dataclass(slots=True)
class ParsedRepository:
    meta: ExportMeta
    structure: List[FileEntry]
    files: Iterator[RestoreEntry]


# ---- Processing pipeline input/output ----

@dataclass(frozen=True, slots=True)
class ProcessingInput:
    """
    Immutable input for a single file processing pipeline.

    Contains the file entry and any global configuration that may be needed
    by steps. Currently only the entry is required; additional fields can be
    added in the future without breaking existing steps.
    """
    entry: FileEntry


@dataclass(slots=True)
class ProcessingResult:
    """
    Mutable result container for a single file processing pipeline.

    Steps read from ProcessingInput and write to this object. The pipeline
    stops early if should_stop is set to True.
    """
    classification: Optional[ClassificationResult] = None
    payload: Optional[FilePayload] = None
    token_count: Optional[int] = None

    should_stop: bool = False
    is_success: bool = False
    skip_code: Optional[SkipCode] = None
    error_code: Optional[ErrorCode] = None
    message: Optional[str] = None

    # Arbitrary metadata for extensions
    metadata: Dict[str, Any] = field(default_factory=dict)