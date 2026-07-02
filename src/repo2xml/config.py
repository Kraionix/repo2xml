# src/repo2xml/config.py
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

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


# ----------------------------------------------------------------------
# Sub-configs (logical groups)
# ----------------------------------------------------------------------

@dataclass(slots=True)
class ScanConfig:
    """Base configuration for scanning – common parameters for all sources."""
    source: str = "filesystem"
    ignore_patterns: List[str] = field(default_factory=list)
    include_patterns: List[str] = field(default_factory=list)

    def normalize(self) -> None:
        self.source = self.source.strip().lower()

    def validate(self) -> None:
        if not self.source:
            raise ConfigurationError("source must not be empty")
        for pat in self.include_patterns:
            if pat.startswith("!"):
                raise ConfigurationError(f"Include pattern '{pat}' must not start with '!'.")

    def validate_environment(self) -> None:
        pass  # No external dependencies for base config


@dataclass(slots=True)
class FilesystemScanConfig(ScanConfig):
    """Scan configuration for local filesystem source."""
    use_gitignore: bool = True
    follow_symlinks_dirs: bool = False
    symlinks_files: SymlinkFilesMode = SymlinkFilesMode.follow
    hard_exclude_dirs: List[str] = field(default_factory=lambda: [".git"])

    def validate(self) -> None:
        ScanConfig.validate(self)  # Call parent method explicitly
        # Additional filesystem-specific structural checks if needed
        # (currently none)

    def validate_environment(self) -> None:
        ScanConfig.validate_environment(self)
        # No external dependencies for filesystem scanning


@dataclass(slots=True)
class GitScanConfig(ScanConfig):
    """Scan configuration for Git source. (Not yet implemented)"""
    # TODO: Add Git-specific parameters like commit_range, include_untracked, etc.
    pass


@dataclass(slots=True)
class S3ScanConfig(ScanConfig):
    """Scan configuration for S3 source. (Not yet implemented)"""
    # TODO: Add S3-specific parameters like bucket, prefix, endpoint_url, etc.
    pass


@dataclass(slots=True)
class FilterConfig:
    """File size and modification time filters."""
    min_file_size: int = 0
    max_file_size: int = 0
    newer_than: Optional[float] = None
    older_than: Optional[float] = None

    def validate(self) -> None:
        if self.min_file_size < 0:
            raise ConfigurationError("min_file_size must be >= 0")
        if self.max_file_size < 0:
            raise ConfigurationError("max_file_size must be >= 0")
        if self.min_file_size > 0 and self.max_file_size > 0 and self.min_file_size > self.max_file_size:
            raise ConfigurationError("min_file_size must be <= max_file_size")

    def validate_environment(self) -> None:
        pass


@dataclass(slots=True)
class OutputFormatConfig:
    """Output formatting and metadata emission."""
    formatting: Formatting = Formatting.compact
    include_timestamp: bool = True
    include_mtime: bool = True
    include_size: bool = True
    root_path_mode: RootPathMode = RootPathMode.absolute
    write_buffer_chars: int = 64_000

    def validate(self) -> None:
        if self.write_buffer_chars < 0:
            raise ConfigurationError("write_buffer_chars must be >= 0")

    def validate_environment(self) -> None:
        pass


@dataclass(slots=True)
class BinaryHandlingConfig:
    """How to handle binary files."""
    mode: BinaryMode = BinaryMode.skip
    max_base64_size: int = 100_000
    max_hash_size: int = 0   # 0 means no limit (hash always computed)

    def validate(self) -> None:
        if self.max_base64_size < 0:
            raise ConfigurationError("max_base64_size must be >= 0")
        if self.max_hash_size < 0:
            raise ConfigurationError("max_hash_size must be >= 0")

    def validate_environment(self) -> None:
        pass


@dataclass(slots=True)
class TextHandlingConfig:
    """Text file reading and decoding."""
    max_text_size: int = 100_000
    newline: NewlineMode = NewlineMode.preserve
    decode_errors: DecodeErrors = DecodeErrors.replace

    def validate(self) -> None:
        if self.max_text_size < 0:
            raise ConfigurationError("max_text_size must be >= 0")

    def validate_environment(self) -> None:
        pass


@dataclass(slots=True)
class RedactConfig:
    """Secret redaction settings."""
    enabled: bool = False
    config_path: Optional[Path] = None

    def validate(self) -> None:
        pass  # Structural checks only – file existence is environment-dependent

    def validate_environment(self) -> None:
        if self.config_path is not None and not self.config_path.is_file():
            raise ConfigurationError(f"Redact config file does not exist: {self.config_path}")


@dataclass(slots=True)
class ClassifyConfig:
    """Classification rules (text vs binary)."""
    config_path: Optional[Path] = None

    def validate(self) -> None:
        pass

    def validate_environment(self) -> None:
        if self.config_path is not None and not self.config_path.is_file():
            raise ConfigurationError(f"Classify config file does not exist: {self.config_path}")


@dataclass(slots=True)
class TokenCountConfig:
    """Token counting settings (Hugging Face)."""
    enabled: bool = False
    model: str = "deepseek-ai/DeepSeek-V4-Pro"
    revision: str = "main"
    trust_remote_code: bool = False
    token: Optional[str] = None

    def validate(self) -> None:
        pass  # Structural checks – currently none

    def validate_environment(self) -> None:
        if self.enabled:
            try:
                import transformers  # noqa: F401
            except ImportError:
                raise ConfigurationError(
                    "Token counting requires the 'transformers' library. "
                    "Install with: pip install repo2xml[tokens]"
                )


# ----------------------------------------------------------------------
# Partition configuration
# ----------------------------------------------------------------------

@dataclass(slots=True)
class PartitionConfig:
    """
    Configuration for splitting the export output into multiple parts.
    """
    enabled: bool = False
    max_tokens_per_part: int = 32000
    output_pattern: Optional[str] = "context_part_{n:03d}.xml"
    clipboard_mode: bool = False
    include_part_stats: bool = True

    def validate(self) -> None:
        if self.enabled:
            if self.max_tokens_per_part <= 0:
                raise ConfigurationError("max_tokens_per_part must be > 0")
            if not self.clipboard_mode and not self.output_pattern:
                raise ConfigurationError("output_pattern must be provided when clipboard_mode is False")

    def validate_environment(self) -> None:
        pass


# ----------------------------------------------------------------------
# Main ExportConfig – aggregates all sub-configs
# ----------------------------------------------------------------------

@dataclass(slots=True)
class ExportConfig:
    """Complete export configuration."""
    mode: Mode = Mode.full
    format: str = "xml"
    scan: ScanConfig = field(default_factory=ScanConfig)  # polymorphic
    filter: FilterConfig = field(default_factory=FilterConfig)
    output: OutputFormatConfig = field(default_factory=OutputFormatConfig)
    binary: BinaryHandlingConfig = field(default_factory=BinaryHandlingConfig)
    text: TextHandlingConfig = field(default_factory=TextHandlingConfig)
    redact: RedactConfig = field(default_factory=RedactConfig)
    classify: ClassifyConfig = field(default_factory=ClassifyConfig)
    token: TokenCountConfig = field(default_factory=TokenCountConfig)
    partition: PartitionConfig = field(default_factory=PartitionConfig)

    def normalize(self) -> None:
        self.format = (self.format or "xml").strip().lower()
        self.scan.normalize()

    def validate(self) -> None:
        """Validate structural invariants only (no environment checks)."""
        if not self.format:
            raise ConfigurationError("format must not be empty")
        self.scan.validate()
        self.filter.validate()
        self.output.validate()
        self.binary.validate()
        self.text.validate()
        self.redact.validate()
        self.classify.validate()
        self.token.validate()
        self.partition.validate()

    def validate_environment(self) -> None:
        """Validate external dependencies (libraries, files) for all sub-configs."""
        self.scan.validate_environment()
        self.filter.validate_environment()
        self.output.validate_environment()
        self.binary.validate_environment()
        self.text.validate_environment()
        self.redact.validate_environment()
        self.classify.validate_environment()
        self.token.validate_environment()
        self.partition.validate_environment()

    def validate_all(self) -> None:
        """Run both structural and environment validation."""
        self.validate()
        self.validate_environment()


# ----------------------------------------------------------------------
# RestoreConfig
# ----------------------------------------------------------------------

@dataclass(slots=True)
class RestoreConfig:
    format: str = "xml"
    overwrite: bool = False
    restore_mtime: bool = True
    create_empty_for_missing: bool = False
    strict_validation: bool = True
    allow_absolute_symlinks: bool = False

    def normalize(self) -> None:
        self.format = (self.format or "xml").strip().lower()

    def validate(self) -> None:
        if not self.format:
            raise ConfigurationError("format must not be empty")