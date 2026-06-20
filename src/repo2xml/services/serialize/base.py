# src/repo2xml/services/serialize/base.py
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Callable, Dict, Protocol, Sequence, Type

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


class PayloadDispatcher:
    """
    A registry-based dispatcher for serializing FilePayload variants.

    Subclasses register handlers for each concrete payload type.
    The dispatch method looks up the handler based on the type of the payload.
    """

    def __init__(self) -> None:
        self._handlers: Dict[Type[FilePayload], Callable[..., None]] = {}

    def register(self, payload_type: Type[FilePayload], handler: Callable[..., None]) -> None:
        self._handlers[payload_type] = handler

    def dispatch(self, payload: FilePayload, entry: FileEntry, write: WriteFn) -> None:
        handler = self._handlers.get(type(payload))
        if handler is None:
            raise TypeError(f"No handler registered for payload type {type(payload).__name__}")
        handler(entry, payload, write)


class BaseSerializer(ABC):
    """
    Abstract base serializer providing common formatting logic and a payload dispatcher.

    Subclasses only need to implement the format‑specific write_* methods
    and register payload handlers.
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

        self.payload_dispatcher = PayloadDispatcher()
        self._register_payload_handlers()

    def _register_payload_handlers(self) -> None:
        """Override in subclasses to register handlers for each payload type."""
        pass

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

    def write_file(self, entry: FileEntry, payload: FilePayload, write: WriteFn) -> None:
        """Default implementation delegates to the payload dispatcher."""
        self.payload_dispatcher.dispatch(payload, entry, write)

    @abstractmethod
    def write_files_close(self, write: WriteFn) -> None:
        ...