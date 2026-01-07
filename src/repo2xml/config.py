from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import List


class Mode(str, Enum):
    """High-level output mode."""
    full = "full"          # structure + content
    metadata = "metadata"  # structure + metadata (no content reads)
    structure = "structure"  # only project structure


class BinaryMode(str, Enum):
    """How to represent binary files when encountered."""
    skip = "skip"
    base64 = "base64"
    hash = "hash"


class NewlineMode(str, Enum):
    """How to normalize newlines for text files."""
    preserve = "preserve"
    lf = "lf"


class Formatting(str, Enum):
    """XML formatting style."""
    compact = "compact"  # newlines, no indentation (default)
    pretty = "pretty"    # newlines + TAB indentation
    minify = "minify"    # no newlines, no indentation


class SymlinkFilesMode(str, Enum):
    """How to treat symlink files."""
    follow = "follow"     # read the target (normal file behavior)
    skip = "skip"         # skip symlink files entirely
    as_link = "as-link"   # emit metadata only + link target, no content reads


@dataclass(slots=True)
class Repo2XMLConfig:
    """
    Configuration DTO for the Repo2XML engine.
    Decouples the core logic from CLI arguments.
    """
    mode: Mode = Mode.full
    formatting: Formatting = Formatting.compact
    binary: BinaryMode = BinaryMode.skip
    newline: NewlineMode = NewlineMode.preserve

    # Meta output
    include_timestamp: bool = True

    # Filtering
    use_gitignore: bool = True
    ignore_patterns: List[str] = field(default_factory=list)
    include_patterns: List[str] = field(default_factory=list)
    hard_exclude_dirs: List[str] = field(default_factory=lambda: [".git"])

    # Symlinks / Traversal
    follow_symlinks_dirs: bool = False
    symlinks_files: SymlinkFilesMode = SymlinkFilesMode.follow

    # Ingestion limits
    max_file_size: int = 100_000