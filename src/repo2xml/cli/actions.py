# src/repo2xml/cli/actions.py
"""Orchestration logic called by the CLI entry point."""
from __future__ import annotations

import logging
import time
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import List, Optional

import typer
from rich.console import Console

from repo2xml.application.progress import NullProgressReporter, RichProgressReporter
from repo2xml.cli.reporting import build_tree, print_breakdown
from repo2xml.cli.ui import LogLevel
from repo2xml.config import (
    BinaryMode,
    DecodeErrors,
    Formatting,
    Mode,
    NewlineMode,
    Repo2XMLConfig,
    RootPathMode,
    SymlinkFilesMode,
)
from repo2xml.domain.exceptions import ConfigurationError, OutputError, Repo2XMLError, SerializationError
from repo2xml.facade import Repo2XML
from repo2xml.services.ingest.redact import redact_secrets
from repo2xml.services.output.targets import (
    ClipboardTarget,
    CompressMode,
    DevNullTarget,
    FileTarget,
    OutputTarget,
    StdoutTarget,
)
from repo2xml.utils.paths import try_relpath_posix
from repo2xml.utils.version import tool_version

logger = logging.getLogger("repo2xml.cli")


def _select_target(
    *,
    stdout: bool,
    clipboard: bool,
    stats_only: bool,
    output_path: Path,
    compress: CompressMode,
) -> OutputTarget:
    if stats_only:
        return DevNullTarget()
    if clipboard:
        return ClipboardTarget()
    if stdout:
        return StdoutTarget(compress=compress)
    return FileTarget(output_path, compress=compress)


def execute(
    *,
    console: Console,
    version: bool,
    path: Path,
    output: Path,
    stdout: bool,
    clipboard: bool,
    stats_only: bool,
    compress: CompressMode,
    formatting: Formatting,
    mode: Mode,
    no_timestamp: bool,
    no_mtime: bool,
    no_size: bool,
    root_path_mode: RootPathMode,
    ext_binary_detect: bool,
    binary_ext_add: Optional[List[str]],
    binary_ext_remove: Optional[List[str]],
    dry_run: bool,
    progress: bool,
    report: bool,
    redact: bool,
    log_level: LogLevel,
    validate_xml: bool,
    quiet: bool,
    no_color: bool,
    size_min: int,
    size_max: int,
    newer_than: Optional[str],
    older_than: Optional[str],
    gitignore: bool,
    ignore: Optional[List[str]],
    include: Optional[List[str]],
    hard_exclude: List[str],
    follow_symlinks_dirs: bool,
    symlinks_files: SymlinkFilesMode,
    max_size: int,
    binary: BinaryMode,
    newline: NewlineMode,
    decode_errors: DecodeErrors,
) -> None:
    """Run the full repo2xml workflow with the given parameters."""
    if version:
        typer.echo(f"repo2xml {tool_version('repo2xml')}")
        raise typer.Exit(code=0)

    if quiet:
        progress = False
        log_level = LogLevel.error

    root = path.resolve()

    if validate_xml:
        if stdout or clipboard or stats_only:
            logger.warning("--validate-xml is only supported with file output. Skipping validation.")
            validate_xml = False
        elif compress != CompressMode.none:
            logger.error(
                "--validate-xml cannot be used with --compress. "
                "Either disable compression or omit --validate-xml."
            )
            raise typer.Exit(code=2)

    out_abs = output.resolve() if output.is_absolute() else (Path.cwd() / output).resolve()
    user_ignore = list(ignore) if ignore else []

    if not stdout and not clipboard and not stats_only:
        rel_out = try_relpath_posix(out_abs, root)
        if rel_out is not None:
            user_ignore.append("/" + rel_out)

    from repo2xml.cli.params import parse_datetime_arg

    newer_ts: Optional[float] = None
    if newer_than:
        newer_ts = parse_datetime_arg(newer_than)
    older_ts: Optional[float] = None
    if older_than:
        older_ts = parse_datetime_arg(older_than)

    processors = []
    if redact:
        processors.append(redact_secrets)

    try:
        config = Repo2XMLConfig(
            format="xml",
            mode=mode,
            formatting=formatting,
            binary=binary,
            newline=newline,
            decode_errors=decode_errors,
            include_timestamp=not no_timestamp,
            root_path_mode=root_path_mode,
            include_mtime=not no_mtime,
            include_size=not no_size,
            binary_ext_fastpath=ext_binary_detect,
            binary_ext_add=list(binary_ext_add) if binary_ext_add else [],
            binary_ext_remove=list(binary_ext_remove) if binary_ext_remove else [],
            use_gitignore=gitignore,
            ignore_patterns=user_ignore,
            include_patterns=list(include) if include else [],
            hard_exclude_dirs=hard_exclude,
            follow_symlinks_dirs=follow_symlinks_dirs,
            symlinks_files=symlinks_files,
            max_text_size=max_size,
            max_base64_size=max_size,
            max_hash_size=0,
            report=report,
            text_processors=processors,
            min_file_size=size_min,
            max_file_size=size_max,
            newer_than=newer_ts,
            older_than=older_ts,
        )
        engine = Repo2XML(root, config)
    except ConfigurationError as e:
        logger.error("Configuration error: %s", e)
        raise typer.Exit(code=2)

    if dry_run:
        logger.info("Dry-run mode: showing filtered project tree.")
        try:
            entries = engine.filtered_scan()
            if entries:
                build_tree(entries, console)
            else:
                console.print("[yellow]No files matched the given filters.[/yellow]")
        except KeyboardInterrupt:
            logger.warning("Interrupted.")
            raise typer.Exit(code=130)
        return

    target = _select_target(
        stdout=stdout,
        clipboard=clipboard,
        stats_only=stats_only,
        output_path=out_abs,
        compress=compress,
    )

    reporter = RichProgressReporter(no_color=no_color) if progress else NullProgressReporter()

    start_time = time.time()
    try:
        with target.open() as out_stream:
            stats = engine.export(out_stream, progress=reporter)

        elapsed = time.time() - start_time

        if stats_only:
            logger.info("Done. Output discarded (%s).", target.describe())
        elif stdout:
            pass
        else:
            logger.info("Done. Output written to: %s", target.describe())

        logger.info(
            "Stats: total=%d, emitted=%d, skipped=%d, errors=%d",
            stats.files_total,
            stats.files_emitted,
            stats.files_skipped,
            stats.files_errors,
        )
        logger.info("Completed in %.2f seconds", elapsed)
        if stats.scan_warning_summary:
            logger.warning("Scan warnings: %s", stats.scan_warning_summary)

        if report:
            print_breakdown("Skipped by cause", stats.skipped_by_code, console)
            print_breakdown("Errors by cause", stats.errors_by_code, console)

        if validate_xml:
            xml_path = out_abs
            try:
                ET.parse(xml_path)
                logger.info("XML validation passed: %s", xml_path)
            except ET.ParseError as e:
                logger.error("XML validation failed for %s: %s", xml_path, e)
                raise typer.Exit(code=3)
            except Exception as e:
                logger.error("Cannot validate XML file %s: %s", xml_path, e)
                raise typer.Exit(code=3)

    except KeyboardInterrupt:
        logger.warning("Interrupted.")
        raise typer.Exit(code=130)
    except (OutputError, SerializationError) as e:
        logger.error("%s", e)
        raise typer.Exit(code=3)
    except Repo2XMLError as e:
        logger.error("Fatal error: %s", e)
        raise typer.Exit(code=1)
    except Exception as e:
        logger.error("Unexpected error: %s", e)
        raise typer.Exit(code=1)