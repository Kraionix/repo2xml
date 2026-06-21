# src/repo2xml/cli/main.py
from __future__ import annotations

from pathlib import Path
from typing import List, Optional

import typer
from rich.console import Console

from repo2xml.cli.actions import execute_export, execute_restore
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
    version: bool = typer.Option(False, "--version", "-V", help="Show version and exit.", is_eager=True),
    path: Path = typer.Argument(".", help="Root path of the project to serialize.", exists=True, file_okay=False, dir_okay=True, resolve_path=True),
    output: Path = typer.Option("context.xml", "--output", "-o", help="Output path (ignored if --stdout/--clipboard/--stats-only)."),
    stdout: bool = typer.Option(False, "--stdout", help="Write output to stdout."),
    clipboard: bool = typer.Option(False, "--clipboard", "-c", help="Copy output to system clipboard instead of file."),
    stats_only: bool = typer.Option(False, "--stats-only", help="Compute and print statistics only."),
    compress: CompressMode = typer.Option(CompressMode.none, "--compress", help="Compression for the output stream."),
    formatting: Formatting = typer.Option(Formatting.compact, "--formatting", help="Output formatting."),
    mode: Mode = typer.Option(Mode.full, "--mode", help="Output mode."),
    no_timestamp: bool = typer.Option(False, "--no-timestamp", help="Do not emit generated_at_utc."),
    no_mtime: bool = typer.Option(False, "--no-mtime", help="Do not emit mtime_utc."),
    no_size: bool = typer.Option(False, "--no-size", help="Do not emit size attributes."),
    root_path_mode: RootPathMode = typer.Option(RootPathMode.absolute, "--root-path-mode", help="How to represent <root_path>."),
    ext_binary_detect: bool = typer.Option(True, "--ext-binary-detect/--no-ext-binary-detect", help="Fast-path binary detection by extension."),
    binary_ext_add: Optional[List[str]] = typer.Option(None, "--binary-ext-add", help="Extra binary extensions."),
    binary_ext_remove: Optional[List[str]] = typer.Option(None, "--binary-ext-remove", help="Remove extensions from binary set."),
    dry_run: bool = typer.Option(False, "--dry-run", help="Show filtered project tree without generating output."),
    progress: bool = typer.Option(True, "--progress/--no-progress", help="Show progress bars."),
    report: bool = typer.Option(False, "--report/--no-report", help="Print detailed skip/error breakdown."),
    redact: bool = typer.Option(False, "--redact-secrets/--no-redact-secrets", help="Redact secrets."),
    log_level: LogLevel = typer.Option(LogLevel.info, "--log-level", help="Logging verbosity."),
    validate_xml: bool = typer.Option(False, "--validate-xml", help="Validate the generated XML."),
    quiet: bool = typer.Option(False, "--quiet", "-q", help="Suppress non-error output."),
    no_color: bool = typer.Option(False, "--no-color", help="Disable colored output."),
    size_min: int = typer.Option(0, "--size-min", help="Ignore files smaller than this (bytes)."),
    size_max: int = typer.Option(0, "--size-max", help="Ignore files larger than this (bytes)."),
    newer_than: Optional[str] = typer.Option(None, "--newer-than", help="Ignore files older than date (ISO-8601)."),
    older_than: Optional[str] = typer.Option(None, "--older-than", help="Ignore files newer than date (ISO-8601)."),
    gitignore: bool = typer.Option(True, "--gitignore/--no-gitignore", help="Respect .gitignore files."),
    ignore: Optional[List[str]] = typer.Option(None, "--ignore", "-i", help="Additional ignore patterns."),
    include: Optional[List[str]] = typer.Option(None, "--include", help="Additional include patterns."),
    hard_exclude: List[str] = typer.Option([".git"], "--hard-exclude", help="Directory names to always exclude."),
    follow_symlinks_dirs: bool = typer.Option(False, "--follow-symlinks-dirs/--no-follow-symlinks-dirs"),
    symlinks_files: SymlinkFilesMode = typer.Option(SymlinkFilesMode.follow, "--symlinks-files", help="How to handle symlink files."),
    max_size: int = typer.Option(100_000, "--max-size", help="Max size in bytes for embedding text/base64 content."),
    binary: BinaryMode = typer.Option(BinaryMode.skip, "--binary", help="How to handle binary files."),
    newline: NewlineMode = typer.Option(NewlineMode.preserve, "--newline", help="Newline normalization."),
    decode_errors: DecodeErrors = typer.Option(DecodeErrors.replace, "--decode-errors", help="Text decoding errors policy."),
) -> None:
    """repo2xml: convert a repository into a single context document for LLM ingestion."""
    console = Console(no_color=no_color)
    logger = setup_logging(log_level, no_color=no_color)
    execute_export(
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


@app.command("restore")
def restore(
    xml_file: Path = typer.Argument(..., help="Input XML file to restore from."),
    output: Path = typer.Option(Path("."), "--output", "-o", help="Target directory for restored files."),
    overwrite: bool = typer.Option(False, "--overwrite", help="Overwrite existing files."),
    no_mtime: bool = typer.Option(False, "--no-mtime", help="Do not restore modification times."),
    create_empty: bool = typer.Option(False, "--create-empty", help="Create empty files for missing content."),
    report: bool = typer.Option(False, "--report", help="Print detailed report."),
    quiet: bool = typer.Option(False, "--quiet", "-q", help="Suppress non-error output."),
    no_color: bool = typer.Option(False, "--no-color", help="Disable colored output."),
) -> None:
    """Restore a repository from a repo2xml XML export."""
    console = Console(no_color=no_color)
    logger = setup_logging(LogLevel.info if not quiet else LogLevel.error, no_color=no_color)
    execute_restore(
        console=console,
        xml_file=xml_file,
        output=output,
        overwrite=overwrite,
        restore_mtime=not no_mtime,
        create_empty=create_empty,
        report=report,
    )