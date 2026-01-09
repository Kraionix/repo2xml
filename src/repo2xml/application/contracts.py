from __future__ import annotations

from pathlib import Path
from typing import Generator, Iterable, Optional, Protocol

from repo2xml.domain.model import FileEntry, SniffResult, TextReadResult


class ScanStatsLike(Protocol):
    """Minimal scanner stats contract (optional)."""

    def has_issues(self) -> bool:
        ...

    def summary(self) -> str:
        ...


class ScannerLike(Protocol):
    """Minimal scanner contract for the pipeline."""

    stats: Optional[ScanStatsLike]

    def scan(self) -> Generator[FileEntry, None, None]:
        ...


class IngestorLike(Protocol):
    """Minimal ingestor contract for the pipeline."""

    def sniff(self, path: Path) -> SniffResult:
        ...

    def read_text(self, path: Path, *, max_size: int) -> TextReadResult:
        ...

    def sha256_file(self, path: Path, *, chunk_size: int = 1024 * 64) -> str:
        ...

    def iter_base64_chunks(self, path: Path, *, chunk_size: int = 1024 * 64) -> Iterable[str]:
        ...