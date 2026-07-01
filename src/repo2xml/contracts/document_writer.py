# src/repo2xml/contracts/document_writer.py
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Callable, List, Optional

from repo2xml.domain.model import ExportMeta, FileEntry, FilePayload, TokenStats

WriteFn = Callable[[str], None]


# ABC is used here because this interface has many methods and serves as a base for format-specific writers.
class DocumentWriter(ABC):
    """
    Abstract interface for writing a complete output document.

    The document consists of:
    - A header with metadata (begin_document)
    - A directory structure (write_structure)
    - A section containing file entries (begin/end_files_section, write_file)
    - Aggregated statistics (write_statistics)
    - A footer (end_document)

    Methods are called in a strict order by WriterCoordinator.
    """

    @abstractmethod
    def begin_document(self, meta: ExportMeta) -> None:
        """Write the document header and any opening markup."""
        ...

    @abstractmethod
    def write_structure(self, entries: List[FileEntry]) -> None:
        """Write the hierarchical project structure (directory tree)."""
        ...

    @abstractmethod
    def begin_files_section(self, mode: str) -> None:
        """Open the section that contains individual file entries."""
        ...

    @abstractmethod
    def write_file(self, entry: FileEntry, payload: FilePayload, token_count: Optional[int] = None) -> None:
        """Write a single file entry with its payload."""
        ...

    @abstractmethod
    def end_files_section(self) -> None:
        """Close the file entries section."""
        ...

    @abstractmethod
    def write_statistics(self, stats: Optional[TokenStats]) -> None:
        """Write aggregated statistics (e.g., total token count)."""
        ...

    @abstractmethod
    def end_document(self) -> None:
        """Write the document footer and any closing markup."""
        ...

    @abstractmethod
    def set_write_fn(self, write_fn: WriteFn) -> None:
        """Set the write function to be used for output."""
        ...