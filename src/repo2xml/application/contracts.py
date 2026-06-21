# src/repo2xml/application/contracts.py
from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import BinaryIO, Generator, Iterable, Iterator, List, Optional, Protocol, Set, Type

from repo2xml.domain.model import (
    ExportMeta,
    FileEntry,
    FilePayload,
    ParsedRepository,
    RestoreEntry,
    RestoreMeta,
    RestoreStats,
    SniffResult,
    TextReadResult,
)
from repo2xml.services.scan.gitignore import IgnoreRuleset


# ----------------------------------------------------------------------
# Existing infrastructure contracts (unchanged)
# ----------------------------------------------------------------------

class ScanStatsLike(Protocol):
    def has_issues(self) -> bool: ...
    def summary(self) -> str: ...


class ScannerLike(Protocol):
    stats: Optional[ScanStatsLike]
    def scan(self) -> Generator[FileEntry, None, None]: ...


class IngestorLike(Protocol):
    def sniff(self, path: Path) -> SniffResult: ...
    def read_text(self, path: Path, *, max_size: int) -> TextReadResult: ...
    def sha256_file(self, path: Path, *, chunk_size: int = 1024 * 64) -> str: ...
    def iter_base64_chunks(self, path: Path, *, chunk_size: int = 1024 * 64) -> Iterable[str]: ...


class IgnoreProvider(Protocol):
    def base_ruleset(self) -> IgnoreRuleset: ...
    def load_dir_ruleset(self, *, dir_abs: Path, dir_rel_posix: str) -> Optional[IgnoreRuleset]: ...
    def is_ignored(self, *, rel_path_posix: str, is_dir: bool, stack: List[IgnoreRuleset]) -> bool: ...


class ProgressReporter(Protocol):
    def set_total(self, total: Optional[int]) -> None: ...
    def advance(self, n: int = 1) -> None: ...
    def finish(self) -> None: ...
    def set_description(self, desc: str) -> None: ...
    def set_phase(self, phase: str) -> None: ...
    def set_warning_count(self, count: int) -> None: ...
    def set_postfix(self, text: str) -> None: ...


# ----------------------------------------------------------------------
# Serialiser / Deserialiser abstractions (format-agnostic)
# ----------------------------------------------------------------------

class Serializer(ABC):
    """Abstract serialiser for a specific format.

    Subclasses MUST implement all write_* methods for every FilePayload
    variant.  If a format does not support a particular payload, the
    implementation should raise UnsupportedPayloadError.
    """

    @abstractmethod
    def write_header(self, meta: ExportMeta, write: 'WriteFn') -> None: ...
    @abstractmethod
    def write_footer(self, write: 'WriteFn') -> None: ...
    @abstractmethod
    def write_structure(self, entries: List[FileEntry], write: 'WriteFn') -> None: ...
    @abstractmethod
    def write_files_open(self, mode: str, write: 'WriteFn') -> None: ...
    @abstractmethod
    def write_files_close(self, write: 'WriteFn') -> None: ...

    # Payload-specific methods (one per concrete payload type)
    @abstractmethod
    def write_metadata(self, entry: FileEntry, payload: 'MetadataPayload', write: 'WriteFn') -> None: ...
    @abstractmethod
    def write_text(self, entry: FileEntry, payload: 'TextPayload', write: 'WriteFn') -> None: ...
    @abstractmethod
    def write_binary_base64(self, entry: FileEntry, payload: 'BinaryBase64Payload', write: 'WriteFn') -> None: ...
    @abstractmethod
    def write_binary_hash(self, entry: FileEntry, payload: 'BinaryHashPayload', write: 'WriteFn') -> None: ...
    @abstractmethod
    def write_link(self, entry: FileEntry, payload: 'LinkPayload', write: 'WriteFn') -> None: ...
    @abstractmethod
    def write_skipped(self, entry: FileEntry, payload: 'SkippedPayload', write: 'WriteFn') -> None: ...
    @abstractmethod
    def write_error(self, entry: FileEntry, payload: 'ErrorPayload', write: 'WriteFn') -> None: ...


class Deserializer(ABC):
    """Abstract deserialiser for a specific format."""

    @abstractmethod
    def parse(self, stream: BinaryIO) -> ParsedRepository:
        """Read the stream and return a structured representation."""
        ...

    # Optionally, a format can advertise which payload types it can reconstruct.
    @classmethod
    def supported_payload_types(cls) -> Set[Type[FilePayload]]:
        return set()  # default: unknown


# ---- Format factory ----

class FormatFactory(ABC):
    """Creates a Serializer / Deserializer pair for a given format."""

    @abstractmethod
    def create_serializer(self, **kwargs) -> Serializer: ...
    @abstractmethod
    def create_deserializer(self, **kwargs) -> Deserializer: ...

    @classmethod
    def supported_payload_types(cls) -> Set[Type[FilePayload]]:
        return set()