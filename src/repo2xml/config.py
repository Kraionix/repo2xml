from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, List


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


# Text processors are intentionally typed as Callables to keep config lightweight.
# Future: introduce a dedicated protocol if/when processors become a public extension API.
TextProcessor = Callable[[str], str]


@dataclass(slots=True)
class Repo2XMLConfig:
    """
    Configuration DTO for the repo2xml pipeline.

    Design note:
    This config intentionally stays "simple data". Component wiring and orchestration
    happens in the facade/pipeline layers.

    The config can be validated/normalized to enforce invariants early.
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

    # Ingestion limits (split by representation)
    #
    # - max_text_size: maximum size for embedding decoded text content
    # - max_base64_size: maximum size for embedding base64 (binary bytes)
    # - max_hash_size: maximum size for hashing binaries; 0 means "no limit"
    #
    # This split makes it possible to allow hashing large binaries without embedding them.
    max_text_size: int = 100_000
    max_base64_size: int = 100_000
    max_hash_size: int = 0

    # Output write buffering (in characters). Reduces overhead of many small writes.
    # 0 disables additional buffering (TextIOWrapper still buffers at the IO layer).
    write_buffer_chars: int = 64_000

    # If enabled, CLI may print a more detailed report (breakdown of skip/error causes).
    report: bool = False

    # Optional text processors (text-only). Not exposed via CLI by default.
    # Processors are applied in order to ingested text content.
    text_processors: List[TextProcessor] = field(default_factory=list)

    def normalize(self) -> None:
        """
        Normalize configuration fields in-place.

        This should be cheap and safe to call multiple times.
        """
        self.format = (self.format or "xml").strip().lower()

        # Deduplicate hard excludes while preserving order.
        seen: set[str] = set()
        deduped: list[str] = []
        for d in self.hard_exclude_dirs:
            if d not in seen:
                seen.add(d)
                deduped.append(d)
        self.hard_exclude_dirs = deduped

    def validate(self) -> None:
        """
        Validate configuration invariants and raise ValueError on invalid input.

        This is intentionally strict: better to fail early than to produce confusing output.
        """
        if self.max_text_size < 0:
            raise ValueError("max_text_size must be >= 0")
        if self.max_base64_size < 0:
            raise ValueError("max_base64_size must be >= 0")
        if self.max_hash_size < 0:
            raise ValueError("max_hash_size must be >= 0")
        if self.write_buffer_chars < 0:
            raise ValueError("write_buffer_chars must be >= 0")

        if not self.format:
            raise ValueError("format must not be empty")

        # Structure-only mode is compatible with any binary/text settings, but we still
        # validate numeric invariants above.
        # Additional cross-field validation can be added later (e.g. format capabilities).