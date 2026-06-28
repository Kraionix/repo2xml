# src/repo2xml/cli/options.py
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

from repo2xml.config import (
    BinaryHandlingConfig,
    BinaryMode,
    ClassifyConfig,
    DecodeErrors,
    ExportConfig,
    FilterConfig,
    Formatting,
    Mode,
    NewlineMode,
    OutputFormatConfig,
    RedactConfig,
    RootPathMode,
    ScanConfig,
    SymlinkFilesMode,
    TextHandlingConfig,
    TokenCountConfig,
)
from repo2xml.domain.exceptions import ConfigurationError
from repo2xml.services.output.targets import CompressMode
from repo2xml.utils.paths import try_relpath_posix


@dataclass(slots=True)
class ExportOptions:
    """Container for all CLI export options.

    This class replaces the long parameter list in execute_export and
    centralises validation and ExportConfig construction.
    """

    # Paths and output
    path: Path
    output: Path
    stdout: bool = False
    clipboard: bool = False
    stats_only: bool = False

    # Output formatting and compression
    compress: CompressMode = CompressMode.none
    formatting: Formatting = Formatting.compact
    mode: Mode = Mode.full

    # Metadata flags
    no_timestamp: bool = False
    no_mtime: bool = False
    no_size: bool = False
    root_path_mode: RootPathMode = RootPathMode.absolute

    # Behaviour
    dry_run: bool = False
    progress: bool = True
    report: bool = False
    redact: bool = False
    log_level: str = "info"          # will be mapped to LogLevel
    validate_xml: bool = False
    quiet: bool = False
    no_color: bool = False
    verbose_errors: bool = False

    # Filters
    size_min: int = 0
    size_max: int = 0
    newer_than: Optional[str] = None
    older_than: Optional[str] = None

    # Gitignore and scanning
    gitignore: bool = True
    ignore: Optional[List[str]] = None
    include: Optional[List[str]] = None
    hard_exclude: List[str] = field(default_factory=lambda: [".git"])
    follow_symlinks_dirs: bool = False
    symlinks_files: SymlinkFilesMode = SymlinkFilesMode.follow

    # File size and encoding limits
    max_size: int = 100_000
    binary: BinaryMode = BinaryMode.skip
    newline: NewlineMode = NewlineMode.preserve
    decode_errors: DecodeErrors = DecodeErrors.replace

    # Scanner and configs
    source: str = "filesystem"
    source_option: Optional[List[str]] = None
    redact_config: Optional[Path] = None
    classify_config: Optional[Path] = None

    # Token counting
    count_tokens: bool = False
    tokenizer_model: str = "deepseek-ai/DeepSeek-V4-Pro"

    def build_config(self, root: Path) -> ExportConfig:
        """Build and validate an ExportConfig from these options."""
        # Resolve output path
        out_abs = self.output.resolve() if self.output.is_absolute() else (Path.cwd() / self.output).resolve()

        # Build ignore list, adding output file if not writing to special targets
        user_ignore = list(self.ignore) if self.ignore else []
        if not self.stdout and not self.clipboard and not self.stats_only:
            rel_out = try_relpath_posix(out_abs, root)
            if rel_out is not None:
                user_ignore.append("/" + rel_out)

        # Parse datetime strings
        from repo2xml.cli.params import parse_datetime_arg
        newer_ts: Optional[float] = None
        if self.newer_than:
            newer_ts = parse_datetime_arg(self.newer_than)
        older_ts: Optional[float] = None
        if self.older_than:
            older_ts = parse_datetime_arg(self.older_than)

        # Source options
        source_opts = {}
        if self.source_option:
            for item in self.source_option:
                if "=" not in item:
                    raise ConfigurationError(f"Source option must be in key=value format: '{item}'")
                key, _, value = item.partition("=")
                source_opts[key.strip()] = value.strip()

        # Build sub‑configs
        scan = ScanConfig(
            use_gitignore=self.gitignore,
            ignore_patterns=user_ignore,
            include_patterns=list(self.include) if self.include else [],
            hard_exclude_dirs=self.hard_exclude,
            follow_symlinks_dirs=self.follow_symlinks_dirs,
            symlinks_files=self.symlinks_files,
            source=self.source,
            source_options=source_opts,
        )

        filter_ = FilterConfig(
            min_file_size=self.size_min,
            max_file_size=self.size_max,
            newer_than=newer_ts,
            older_than=older_ts,
        )

        output_format = OutputFormatConfig(
            formatting=self.formatting,
            include_timestamp=not self.no_timestamp,
            include_mtime=not self.no_mtime,
            include_size=not self.no_size,
            root_path_mode=self.root_path_mode,
        )

        binary_cfg = BinaryHandlingConfig(
            mode=self.binary,
            max_base64_size=self.max_size,
            max_hash_size=0,
        )

        text_cfg = TextHandlingConfig(
            max_text_size=self.max_size,
            newline=self.newline,
            decode_errors=self.decode_errors,
        )

        redact_cfg = RedactConfig(
            enabled=self.redact,
            config_path=self.redact_config,
        )

        classify_cfg = ClassifyConfig(
            config_path=self.classify_config,
        )

        # Token counting – disabled in dry‑run or stats‑only
        count_enabled = self.count_tokens and not self.dry_run and not self.stats_only
        token_cfg = TokenCountConfig(
            enabled=count_enabled,
            model=self.tokenizer_model,
        )

        config = ExportConfig(
            mode=self.mode,
            format="xml",
            scan=scan,
            filter=filter_,
            output=output_format,
            binary=binary_cfg,
            text=text_cfg,
            redact=redact_cfg,
            classify=classify_cfg,
            token=token_cfg,
        )
        config.normalize()
        config.validate()
        return config

    def validate_export_compatibility(self) -> None:
        """Perform cross‑option validation that cannot be done inside ExportConfig."""
        if self.validate_xml:
            if self.stdout or self.clipboard or self.stats_only:
                raise ConfigurationError(
                    "--validate-xml is only supported with file output."
                )
            if self.compress != CompressMode.none:
                raise ConfigurationError(
                    "--validate-xml cannot be used with --compress. "
                    "Either disable compression or omit --validate-xml."
                )