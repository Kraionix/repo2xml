# src/repo2xml/config.py
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

from repo2xml.domain.exceptions import ConfigurationError


class Mode(str, Enum):
    full = "full"
    metadata = "metadata"
    structure = "structure"


class BinaryMode(str, Enum):
    skip = "skip"
    base64 = "base64"
    hash = "hash"


class NewlineMode(str, Enum):
    preserve = "preserve"
    lf = "lf"


class DecodeErrors(str, Enum):
    replace = "replace"
    strict = "strict"


class Formatting(str, Enum):
    compact = "compact"
    pretty = "pretty"
    minify = "minify"


class SymlinkFilesMode(str, Enum):
    follow = "follow"
    skip = "skip"
    as_link = "as-link"


class RootPathMode(str, Enum):
    absolute = "absolute"
    relative = "relative"
    redact = "redact"


TextProcessor = Callable[[str], str]


@dataclass(slots=True)
class ExportConfig:
    format: str = "xml"
    mode: Mode = Mode.full
    formatting: Formatting = Formatting.compact
    binary: BinaryMode = BinaryMode.skip
    newline: NewlineMode = NewlineMode.preserve
    decode_errors: DecodeErrors = DecodeErrors.replace
    include_timestamp: bool = True
    root_path_mode: RootPathMode = RootPathMode.absolute
    include_mtime: bool = True
    include_size: bool = True
    binary_ext_fastpath: bool = True
    binary_ext_add: List[str] = field(default_factory=list)
    binary_ext_remove: List[str] = field(default_factory=list)
    use_gitignore: bool = True
    ignore_patterns: List[str] = field(default_factory=list)
    include_patterns: List[str] = field(default_factory=list)
    hard_exclude_dirs: List[str] = field(default_factory=lambda: [".git"])
    follow_symlinks_dirs: bool = False
    symlinks_files: SymlinkFilesMode = SymlinkFilesMode.follow
    max_text_size: int = 100_000
    max_base64_size: int = 100_000
    max_hash_size: int = 0
    write_buffer_chars: int = 64_000
    report: bool = False
    text_processors: List[TextProcessor] = field(default_factory=list)
    min_file_size: int = 0
    max_file_size: int = 0
    newer_than: Optional[float] = None
    older_than: Optional[float] = None
    # --- New fields for scanner selection ---
    source: str = "filesystem"                  # Which scanner to use
    source_options: Dict[str, Any] = field(default_factory=dict)  # Extra args for the scanner

    def normalize(self) -> None:
        self.format = (self.format or "xml").strip().lower()
        self.source = self.source.strip().lower()
        seen: set[str] = set()
        deduped: list[str] = []
        for d in self.hard_exclude_dirs:
            if d not in seen:
                seen.add(d)
                deduped.append(d)
        self.hard_exclude_dirs = deduped

    def validate(self) -> None:
        if self.max_text_size < 0:
            raise ConfigurationError("max_text_size must be >= 0")
        if self.max_base64_size < 0:
            raise ConfigurationError("max_base64_size must be >= 0")
        if self.max_hash_size < 0:
            raise ConfigurationError("max_hash_size must be >= 0")
        if self.write_buffer_chars < 0:
            raise ConfigurationError("write_buffer_chars must be >= 0")
        if self.min_file_size < 0:
            raise ConfigurationError("min_file_size must be >= 0")
        if self.max_file_size < 0:
            raise ConfigurationError("max_file_size must be >= 0")
        if self.min_file_size > 0 and self.max_file_size > 0 and self.min_file_size > self.max_file_size:
            raise ConfigurationError("min_file_size must be <= max_file_size")
        if not self.format:
            raise ConfigurationError("format must not be empty")
        for pat in self.include_patterns:
            if pat.startswith("!"):
                raise ConfigurationError(
                    f"Include pattern '{pat}' must not start with '!'."
                )
        if not self.source:
            raise ConfigurationError("source must not be empty")


@dataclass(slots=True)
class RestoreConfig:
    format: str = "xml"
    overwrite: bool = False
    restore_mtime: bool = True
    create_empty_for_missing: bool = False
    strict_validation: bool = True

    def normalize(self) -> None:
        self.format = (self.format or "xml").strip().lower()

    def validate(self) -> None:
        if not self.format:
            raise ConfigurationError("format must not be empty")