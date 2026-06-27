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
    TextReadResult,
    TokenStats,
)
from repo2xml.services.scan.gitignore import IgnoreRuleset
from repo2xml.services.serialize.base import WriteFn   # добавлен импорт


# ----------------------------------------------------------------------
# Existing infrastructure contracts
# ----------------------------------------------------------------------

class ScanStatsLike(Protocol):
    def has_issues(self) -> bool: ...
    def summary(self) -> str: ...


class ScannerLike(Protocol):
    stats: Optional[ScanStatsLike]
    def scan(self) -> Generator[FileEntry, None, None]: ...


class IngestorLike(Protocol):
    """Reduced ingestor interface – classification is handled externally."""
    def read_text(self, path: Path, *, max_size: int, sniff_sample: Optional[bytes] = None) -> TextReadResult: ...
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
# Token counting contracts (new)
# ----------------------------------------------------------------------

class TokenCounter(Protocol):
    """Protocol for token counters."""
    def count(self, text: str, ext: str = "") -> int:
        """Count tokens in text, updating internal stats. Return token count."""
        ...

    def get_stats(self) -> TokenStats:
        """Return accumulated token statistics."""
        ...


class TokenCounterFactory(ABC):
    """Abstract factory for token counters."""
    @abstractmethod
    def create(self, model: str, **kwargs) -> TokenCounter:
        """Create a TokenCounter instance for the given model."""
        ...


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
    def write_header(self, meta: ExportMeta, write: WriteFn) -> None: ...
    @abstractmethod
    def write_footer(self, write: WriteFn) -> None: ...
    @abstractmethod
    def write_structure(self, entries: List[FileEntry], write: WriteFn) -> None: ...
    @abstractmethod
    def write_files_open(self, mode: str, write: WriteFn) -> None: ...
    @abstractmethod
    def write_files_close(self, write: WriteFn) -> None: ...

    # Payload-specific methods (one per concrete payload type)
    @abstractmethod
    def write_metadata(self, entry: FileEntry, payload: 'MetadataPayload', write: WriteFn, token_count: Optional[int] = None) -> None: ...
    @abstractmethod
    def write_text(self, entry: FileEntry, payload: 'TextPayload', write: WriteFn, token_count: Optional[int] = None) -> None: ...
    @abstractmethod
    def write_binary_base64(self, entry: FileEntry, payload: 'BinaryBase64Payload', write: WriteFn, token_count: Optional[int] = None) -> None: ...
    @abstractmethod
    def write_binary_hash(self, entry: FileEntry, payload: 'BinaryHashPayload', write: WriteFn, token_count: Optional[int] = None) -> None: ...
    @abstractmethod
    def write_link(self, entry: FileEntry, payload: 'LinkPayload', write: WriteFn, token_count: Optional[int] = None) -> None: ...
    @abstractmethod
    def write_skipped(self, entry: FileEntry, payload: 'SkippedPayload', write: WriteFn, token_count: Optional[int] = None) -> None: ...
    @abstractmethod
    def write_error(self, entry: FileEntry, payload: 'ErrorPayload', write: WriteFn, token_count: Optional[int] = None) -> None: ...

    @abstractmethod
    def write_statistics(self, token_stats: Optional[TokenStats], write: WriteFn) -> None:
        """Write aggregated statistics (e.g., total tokens) after files section."""
        ...

    # New unified method for writing any file entry.
    @abstractmethod
    def write_file(self, entry: FileEntry, payload: FilePayload, write: WriteFn, token_count: Optional[int] = None) -> None:
        """
        Write a single file entry using the provided payload.

        This method dispatches internally to the appropriate payload-specific
        writer based on the actual type of `payload`. It is the only method
        that higher-level components (e.g., PipelineOrchestrator) should call
        for file entries.
        """
        ...


class Deserializer(ABC):
    """Abstract deserialiser for a specific format."""

    @abstractmethod
    def parse(self, stream: BinaryIO, *, strict: bool = False) -> ParsedRepository:
        """
        Read the stream and return a structured representation.

        If `strict` is True, implementations should perform rigorous
        structural validation and raise DeserializationError on any violation.
        """
        ...

    @classmethod
    def supported_payload_types(cls) -> Set[Type[FilePayload]]:
        return set()


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