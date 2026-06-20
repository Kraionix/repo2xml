# src/repo2xml/cli/main.py
from __future__ import annotations

from pathlib import Path
from typing import List, Optional

import typer
from rich.console import Console

from repo2xml.cli.actions import execute
from repo2xml.cli.ui import LogLevel, setup_logging
from repo2xml.config import (
    BinaryMode,
    DecodeErrors,
    Formatting,
    Mode,
    NewlineMode,
    RootPathMode,
    SymlinkFilesMode,
)
from repo2xml.services.output.targets import CompressMode

app = typer.Typer(add_completion=False)


@app.callback(invoke_without_command=True)
def main(
    version: bool = typer.Option(
        False,
        "--version",
        "-V",
        help="Show version and exit.",
        is_eager=True,
    ),
    path: Path = typer.Argument(
        ".",
        help="Root path of the project to serialize.",
        exists=True,
        file_okay=False,
        dir_okay=True,
        resolve_path=True,
    ),
    output: Path = typer.Option(
        "context.xml",
        "--output",
        "-o",
        help="Output path (ignored if --stdout/--clipboard/--stats-only).",
    ),
    stdout: bool = typer.Option(
        False,
        "--stdout",
        help="Write output to stdout.",
    ),
    clipboard: bool = typer.Option(
        False,
        "--clipboard",
        "-c",
        help="Copy output to system clipboard instead of file.",
    ),
    stats_only: bool = typer.Option(
        False,
        "--stats-only",
        help="Compute and print statistics only (discard generated output).",
    ),
    compress: CompressMode = typer.Option(
        CompressMode.none,
        "--compress",
        help="Compression for the output stream.",
    ),
    formatting: Formatting = typer.Option(
        Formatting.compact,
        "--formatting",
        help="Output formatting.",
    ),
    mode: Mode = typer.Option(
        Mode.full,
        "--mode",
        help="Output mode.",
    ),
    no_timestamp: bool = typer.Option(
        False,
        "--no-timestamp",
        help="Do not emit generated_at_utc (for deterministic output).",
    ),
    no_mtime: bool = typer.Option(
        False,
        "--no-mtime",
        help="Do not emit mtime_utc attributes (for deterministic output).",
    ),
    no_size: bool = typer.Option(
        False,
        "--no-size",
        help="Do not emit size attributes (for deterministic output / privacy).",
    ),
    root_path_mode: RootPathMode = typer.Option(
        RootPathMode.absolute,
        "--root-path-mode",
        help="How to represent <root_path>: absolute|relative|redact.",
    ),
    ext_binary_detect: bool = typer.Option(
        True,
        "--ext-binary-detect/--no-ext-binary-detect",
        help="Fast-path binary detection by file extension (default: enabled).",
    ),
    binary_ext_add: Optional[List[str]] = typer.Option(
        None,
        "--binary-ext-add",
        help="Extra binary extensions for fast-path detection (repeatable). Example: .psd",
    ),
    binary_ext_remove: Optional[List[str]] = typer.Option(
        None,
        "--binary-ext-remove",
        help="Remove extensions from the default binary fast-path set (repeatable). Example: .pdf",
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Show the project tree with all active filters, without generating output.",
    ),
    progress: bool = typer.Option(
        True,
        "--progress/--no-progress",
        help="Show progress bars.",
    ),
    report: bool = typer.Option(
        False,
        "--report/--no-report",
        help="Print a detailed post-run report (breakdown of skip/error causes).",
    ),
    redact: bool = typer.Option(
        False,
        "--redact-secrets/--no-redact-secrets",
        help="Redact common secret patterns from text content before writing output.",
    ),
    log_level: LogLevel = typer.Option(
        LogLevel.info,
        "--log-level",
        help="Logging verbosity.",
    ),
    validate_xml: bool = typer.Option(
        False,
        "--validate-xml",
        help="Validate the generated XML document by parsing it after writing (only for file output).",
    ),
    quiet: bool = typer.Option(
        False,
        "--quiet",
        "-q",
        help="Suppress all non‑error output. Implies --no-progress and --log-level error.",
    ),
    no_color: bool = typer.Option(
        False,
        "--no-color",
        help="Disable colored terminal output (forces plain text).",
    ),
    size_min: int = typer.Option(
        0,
        "--size-min",
        help="Ignore files smaller than this size (bytes). 0 = no limit.",
        min=0,
    ),
    size_max: int = typer.Option(
        0,
        "--size-max",
        help="Ignore files larger than this size (bytes). 0 = no limit.",
        min=0,
    ),
    newer_than: Optional[str] = typer.Option(
        None,
        "--newer-than",
        help="Ignore files modified before this date (ISO‑8601). Example: 2025-01-01T00:00:00Z",
    ),
    older_than: Optional[str] = typer.Option(
        None,
        "--older-than",
        help="Ignore files modified after this date (ISO‑8601).",
    ),
    gitignore: bool = typer.Option(
        True,
        "--gitignore/--no-gitignore",
        help="Respect .gitignore files (default: enabled).",
    ),
    ignore: Optional[List[str]] = typer.Option(
        None,
        "--ignore",
        "-i",
        help="Additional ignore patterns (gitignore syntax). Can be repeated.",
    ),
    include: Optional[List[str]] = typer.Option(
        None,
        "--include",
        help="Additional include patterns (gitignore syntax). Do not start with !. Can be repeated.",
    ),
    hard_exclude: List[str] = typer.Option(
        [".git"],
        "--hard-exclude",
        help="Directory names to always exclude (repeatable). Default: .git",
    ),
    follow_symlinks_dirs: bool = typer.Option(
        False,
        "--follow-symlinks-dirs/--no-follow-symlinks-dirs",
        help="Follow symlinked directories (default: no).",
    ),
    symlinks_files: SymlinkFilesMode = typer.Option(
        SymlinkFilesMode.follow,
        "--symlinks-files",
        help="How to handle symlink files: follow|skip|as-link (default: follow).",
    ),
    max_size: int = typer.Option(
        100_000,
        "--max-size",
        help="Max size in bytes for embedding text/base64 content (larger files are skipped).",
        min=0,
    ),
    binary: BinaryMode = typer.Option(
        BinaryMode.skip,
        "--binary",
        help="How to handle binary files: skip|base64|hash.",
    ),
    newline: NewlineMode = typer.Option(
        NewlineMode.preserve,
        "--newline",
        help="Newline normalization: preserve|lf.",
    ),
    decode_errors: DecodeErrors = typer.Option(
        DecodeErrors.replace,
        "--decode-errors",
        help="Text decoding errors policy: replace|strict.",
    ),
) -> None:
    """repo2xml: convert a repository into a single context document for LLM ingestion."""
    console = Console(no_color=no_color)
    logger = setup_logging(log_level, no_color=no_color)  # noqa: F841  (used in actions)
    execute(
        console=console,
        version=version,
        path=path,
        output=output,
        stdout=stdout,
        clipboard=clipboard,
        stats_only=stats_only,
        compress=compress,
        formatting=formatting,
        mode=mode,
        no_timestamp=no_timestamp,
        no_mtime=no_mtime,
        no_size=no_size,
        root_path_mode=root_path_mode,
        ext_binary_detect=ext_binary_detect,
        binary_ext_add=binary_ext_add,
        binary_ext_remove=binary_ext_remove,
        dry_run=dry_run,
        progress=progress,
        report=report,
        redact=redact,
        log_level=log_level,
        validate_xml=validate_xml,
        quiet=quiet,
        no_color=no_color,
        size_min=size_min,
        size_max=size_max,
        newer_than=newer_than,
        older_than=older_than,
        gitignore=gitignore,
        ignore=ignore,
        include=include,
        hard_exclude=hard_exclude,
        follow_symlinks_dirs=follow_symlinks_dirs,
        symlinks_files=symlinks_files,
        max_size=max_size,
        binary=binary,
        newline=newline,
        decode_errors=decode_errors,
    )