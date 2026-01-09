from __future__ import annotations

from typing import Callable, Protocol, Sequence

from repo2xml.domain.model import ExportMeta, FileEntry, FilePayload


WriteFn = Callable[[str], None]


class Serializer(Protocol):
    """
    Serializer contract.

    Serializers should be streaming-friendly:
    - write fragments to the provided write() callable
    - avoid buffering the whole document in memory

    The contract is intentionally minimal but slightly generalized:
    - Some serializers may not emit a dedicated structure section.
    - Some serializers may not have an explicit <files> container concept.
    """

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