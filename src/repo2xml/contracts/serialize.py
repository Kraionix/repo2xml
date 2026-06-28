# src/repo2xml/contracts/serialize.py
from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import BinaryIO, List, Optional, Set, Type

from repo2xml.domain.model import (
    ExportMeta,
    FileEntry,
    FilePayload,
    ParsedRepository,
    TokenStats,
)
from repo2xml.services.serialize.base import WriteFn


class DocumentMetadataWriter(ABC):
    """Writes document‑level metadata: header, footer, and statistics."""

    @abstractmethod
    def write_header(self, meta: ExportMeta, write: WriteFn) -> None:
        """Write the document header."""
        ...

    @abstractmethod
    def write_footer(self, write: WriteFn) -> None:
        """Write the document footer (closing tags)."""
        ...

    @abstractmethod
    def write_statistics(self, token_stats: Optional[TokenStats], write: WriteFn) -> None:
        """Write aggregated statistics (e.g., total tokens)."""
        ...


class StructureWriter(ABC):
    """Writes the project directory tree structure."""

    @abstractmethod
    def write_structure(self, entries: List[FileEntry], write: WriteFn) -> None:
        """Write the hierarchical project structure."""
        ...


class FileSectionWriter(ABC):
    """Opens and closes the section that contains file entries."""

    @abstractmethod
    def write_files_open(self, mode: str, write: WriteFn) -> None:
        """Open the <files> section with the given mode attribute."""
        ...

    @abstractmethod
    def write_files_close(self, write: WriteFn) -> None:
        """Close the <files> section."""
        ...


class FileContentWriter(ABC):
    """Writes a single file entry with its payload."""

    @abstractmethod
    def write_file(
        self,
        entry: FileEntry,
        payload: FilePayload,
        write: WriteFn,
        token_count: Optional[int] = None,
    ) -> None:
        """Write one file entry."""
        ...


class Deserializer(ABC):
    """Abstract deserialiser for a specific format."""

    @abstractmethod
    def parse(self, stream: BinaryIO, *, strict: bool = False) -> ParsedRepository:
        """Parse the stream into a ParsedRepository."""
        ...

    @classmethod
    def supported_payload_types(cls) -> Set[Type[FilePayload]]:
        return set()


class FormatFactory(ABC):
    """Creates a Serializer / Deserializer pair for a given format."""

    @abstractmethod
    def create_serializer(self, **kwargs) -> (
        DocumentMetadataWriter & StructureWriter & FileSectionWriter & FileContentWriter
    ):
        """Create a serializer instance implementing all four writer interfaces."""
        ...

    @abstractmethod
    def create_deserializer(self, **kwargs) -> Deserializer:
        """Create a deserializer instance."""
        ...

    @classmethod
    def supported_payload_types(cls) -> Set[Type[FilePayload]]:
        return set()