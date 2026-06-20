from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Callable, Protocol, Sequence

from repo2xml.domain.model import ExportMeta, FileEntry, FilePayload

WriteFn = Callable[[str], None]


class Serializer(Protocol):
    """Serializer contract (kept for structural typing compatibility)."""

    @property
    def supports_structure(self) -> bool:
        ...

    @property
    def supports_files_section(self) -> bool:
        ...

    def write_header(self, meta: ExportMeta, write: WriteFn) -> None:
        ...

    def write_structure(self, entries: Sequence[FileEntry], write: WriteFn) -> None:
        ...

    def write_files_open(self, mode: str, write: WriteFn) -> None:
        ...

    def write_file(self, entry: FileEntry, payload: FilePayload, write: WriteFn) -> None:
        ...

    def write_files_close(self, write: WriteFn) -> None:
        ...

    def write_footer(self, write: WriteFn) -> None:
        ...


class BaseSerializer(ABC):
    """
    Abstract base serializer providing common formatting logic.

    Subclasses only need to implement the format‑specific write_* methods.
    """

    def __init__(
        self,
        *,
        formatting: str = "compact",
        include_mtime: bool = True,
        include_size: bool = True,
    ):
        if formatting not in {"compact", "pretty", "minify"}:
            raise ValueError(f"Unknown formatting: {formatting}")

        self.formatting = formatting
        self.include_mtime = include_mtime
        self.include_size = include_size

    # ------------------------------------------------------------------
    # Common properties
    # ------------------------------------------------------------------

    @property
    def nl(self) -> str:
        """Line ending according to formatting style."""
        return "" if self.formatting == "minify" else "\n"

    def indent(self, level: int) -> str:
        """Indentation string (tabs in 'pretty', otherwise empty)."""
        if self.formatting == "pretty":
            return "\t" * level
        return ""

    # ------------------------------------------------------------------
    # Structural defaults (most formats can provide a structure section)
    # ------------------------------------------------------------------

    @property
    def supports_structure(self) -> bool:
        return True

    @property
    def supports_files_section(self) -> bool:
        return True

    # ------------------------------------------------------------------
    # Abstract format‑specific methods
    # ------------------------------------------------------------------

    @abstractmethod
    def write_header(self, meta: ExportMeta, write: WriteFn) -> None:
        ...

    @abstractmethod
    def write_footer(self, write: WriteFn) -> None:
        ...

    @abstractmethod
    def write_structure(self, entries: Sequence[FileEntry], write: WriteFn) -> None:
        ...

    @abstractmethod
    def write_files_open(self, mode: str, write: WriteFn) -> None:
        ...

    @abstractmethod
    def write_file(self, entry: FileEntry, payload: FilePayload, write: WriteFn) -> None:
        ...

    @abstractmethod
    def write_files_close(self, write: WriteFn) -> None:
        ...