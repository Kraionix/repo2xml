from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, List, Optional


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
    """Output formatting style."""
    compact = "compact"  # newlines, no indentation (default)
    pretty = "pretty"    # newlines + TAB indentation
    minify = "minify"    # no newlines, no indentation


class SymlinkFilesMode(str, Enum):
    """How to treat symlink files."""
    follow = "follow"     # read the target (normal file behavior)
    skip = "skip"         # skip symlink files entirely
    as_link = "as-link"   # emit metadata + link target, no content reads


class RootPathMode(str, Enum):
    """
    How to represent <root_path> in the meta block.

    - absolute: full resolved path (default)
    - relative: relative to current working directory when possible
    - redact: hide path completely (privacy-friendly)
    """
    absolute = "absolute"
    relative = "relative"
    redact = "redact"


# Content processors are intentionally typed as Callables to keep config lightweight.
# Future: introduce a dedicated protocol if/when processors become a public extension API.
ContentProcessor = Callable[[str], str]


@dataclass(slots=True)
class Repo2XMLConfig:
    """
    Configuration DTO for the repo2xml pipeline.

    Design note:
    This config intentionally stays "simple data". Component wiring and orchestration
    happens in the facade/pipeline layers.
    """
    # Output selection (future-proof; currently only "xml" is implemented)
    format: str = "xml"

    # Output behavior
    mode: Mode = Mode.full
    formatting: Formatting = Formatting.compact
    binary: BinaryMode = BinaryMode.skip
    newline: NewlineMode = NewlineMode.preserve

    # Meta output
    include_timestamp: bool = True
    root_path_mode: RootPathMode = RootPathMode.absolute

    # Binary detection fast-path
    binary_ext_fastpath: bool = True
    binary_ext_add: List[str] = field(default_factory=list)
    binary_ext_remove: List[str] = field(default_factory=list)

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

    # Optional content processors (text-only). Not exposed via CLI yet.
    # Processors are applied in order to ingested text content.
    text_processors: List[Callable[[str], str]] = field(default_factory=list)