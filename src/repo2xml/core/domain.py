from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass(slots=True)
class FileNode:
    """
    A single file discovered in the repository scan.

    Notes:
    - `path` is the absolute filesystem path used to read the file.
    - `rel_path` is the repository-relative POSIX path used in XML and filtering.
    - For symlinks:
        - `is_symlink` indicates the directory entry is a symlink.
        - `symlink_target` is best-effort and may be None (permission/platform dependent).
    """
    path: Path
    rel_path: str
    name: str
    size: int
    mtime_ns: int
    is_symlink: bool
    symlink_target: Optional[str] = None


@dataclass
class RepoContext:
    """
    Optional execution context container.

    This is currently not used heavily, but kept for future extensibility
    (e.g., shared options/config across layers).
    """
    root_path: Path
    ignore_patterns: list[str] = field(default_factory=list)