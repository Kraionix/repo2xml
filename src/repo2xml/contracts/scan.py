# src/repo2xml/contracts/scan.py
from __future__ import annotations

from pathlib import Path
from typing import Generator, List, Optional, Protocol, Sequence

from repo2xml.domain.ignore import IgnoreRuleset


class ScanStatsLike(Protocol):
    """Protocol for scanner statistics."""
    def has_issues(self) -> bool: ...
    def summary(self) -> str: ...


class ScannerLike(Protocol):
    """Protocol for a filesystem scanner."""
    stats: Optional[ScanStatsLike]

    def scan(self) -> Generator[FileEntry, None, None]:
        """Yield FileEntry objects for all files in the repository."""
        ...


class IgnoreProvider(Protocol):
    """Protocol for providing .gitignore‑style ignore rules."""
    def base_ruleset(self) -> IgnoreRuleset:
        """Return the root‑scoped ruleset."""
        ...

    def load_dir_ruleset(self, *, dir_abs: Path, dir_rel_posix: str) -> Optional[IgnoreRuleset]:
        """Load and compile rules from a directory's .gitignore, if present."""
        ...

    def is_ignored(
        self,
        *,
        rel_path_posix: str,
        is_dir: bool,
        stack: Sequence[IgnoreRuleset],
    ) -> bool:
        """Return True if the path is ignored by any rule in the stack."""
        ...