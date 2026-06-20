# src/repo2xml/application/contracts.py
from __future__ import annotations

from pathlib import Path
from typing import Generator, Iterable, Optional, Protocol, Sequence

from repo2xml.domain.model import FileEntry, SniffResult, TextReadResult
from repo2xml.services.scan.gitignore import IgnoreRuleset


class ScanStatsLike(Protocol):
    """Minimal scanner stats contract."""

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


class IgnoreProvider(Protocol):
    """Minimal ignore provider contract for filesystem scanning."""

    def base_ruleset(self) -> IgnoreRuleset:
        ...

    def load_dir_ruleset(self, *, dir_abs: Path, dir_rel_posix: str) -> Optional[IgnoreRuleset]:
        ...

    def is_ignored(self, *, rel_path_posix: str, is_dir: bool, stack: Sequence[IgnoreRuleset]) -> bool:
        ...