# src/repo2xml/cli/main.py
from __future__ import annotations

import time
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

import typer
from rich.console import Console
from rich.tree import Tree

from repo2xml.application.progress import NullProgressReporter, RichProgressReporter
from repo2xml.cli.ui import LogLevel, setup_logging
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
from repo2xml.domain.model import FileEntry
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

app = typer.Typer(add_completion=False)


def _print_breakdown(title: str, data: dict[str, int], console: Console) -> None:
    if not data:
        return
    from rich.table import Table

    table = Table(title=title, show_header=True, header_style="bold")
    table.add_column("Code", style="dim")
    table.add_column("Count", justify="right")

    for k, v in sorted(data.items(), key=lambda kv: (-kv[1], kv[0])):
        table.add_row(k, str(v))

    console.print(table)


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


def _parse_datetime_arg(value: str) -> float:
    """Parse an ISO‑8601 date/time string into UTC epoch seconds."""
    try:
        dt = datetime.fromisoformat(value)
        if dt.tzinfo is None:
            # Assume UTC if no timezone is given
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.timestamp()
    except (ValueError, OverflowError) as e:
        raise typer.BadParameter(f"Invalid date/time: {e}")


def _build_tree(entries: List[FileEntry], console: Console) -> None:
    """Render the filtered file list as a Rich Tree."""
    tree = Tree("Project structure (dry-run)")
    # Group entries by directory parts
    dirs: dict[tuple[str, ...], list[str]] = {}
    for entry in entries:
        parts = tuple(entry.rel_path.split("/"))
        dir_key = parts[:-1]
        file_name = parts[-1]
        dirs.setdefault(dir_key, []).append(file_name)

    # We need to build a nested tree.  Since Rich Tree allows adding children by path,
    # we can iterate through dirs and add files.
    # The simplest way: sort dirs, then for each directory, add a sub-tree.
    for dir_key in sorted(dirs):
        path_str = "/".join(dir_key)
        node = tree
        if dir_key:
            # add intermediate directories
            current_path = ""
            for part in dir_key:
                current_path = f"{current_path}/{part}" if current_path else part
                # Rich Tree doesn't have a direct lookup; we build dynamically by
                # keeping a reference to the last node for each prefix.  Simpler:
                # use the tree as single root and just add the whole path as a subtree.
                # We'll just add the full relative directory path as a node.
            # Actually we want to reuse existing branches.  We'll maintain a mapping
            # from path tuple to Tree node.
            # Let's implement a proper incremental tree building.
            pass

    # Since Rich Tree doesn't natively support incremental insertion by path,
    # we'll do a simpler approach: build a nested dictionary first, then render.
    root: dict = {}
    for entry in sorted(entries, key=lambda e: e.rel_path):
        parts = entry.rel_path.split("/")
        current = root
        for part in parts[:-1]:
            current = current.setdefault(part, {})
        # leaf: file, store as None or name
        current.setdefault("__files__", []).append(parts[-1])

    def add_branch(tree_node: Tree, subtree: dict) -> None:
        for name, value in sorted(subtree.items()):
            if name == "__files__":
                for fname in sorted(value):
                    tree_node.add(fname)
            else:
                branch = tree_node.add(name)
                add_branch(branch, value)

    add_branch(tree, root)
    console.print(tree)


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
    # --- File-level size & date filters ---
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
    # Filtering options
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
        help="Additional include patterns (gitignore syntax). Can be repeated.",
    ),
    hard_exclude: List[str] = typer.Option(
        [".git"],
        "--hard-exclude",
        help="Directory names to always exclude (repeatable). Default: .git",
    ),
    # Symlink handling
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
    # Ingestion options
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
    """
    repo2xml: convert a repository into a single context document for LLM ingestion.
    """
    if version:
        typer.echo(f"repo2xml {tool_version('repo2xml')}")
        raise typer.Exit(code=0)

    # --quiet forces minimal output
    if quiet:
        progress = False
        log_level = LogLevel.error

    # Setup console with color control
    console = Console(no_color=no_color)
    logger = setup_logging(log_level, no_color=no_color)

    root = path.resolve()

    # Validate --validate-xml compatibility
    if validate_xml:
        if stdout or clipboard or stats_only:
            logger.warning(
                "--validate-xml is only supported with file output. Skipping validation."
            )
            validate_xml = False
        elif compress != CompressMode.none:
            logger.error(
                "--validate-xml cannot be used with --compress. "
                "Either disable compression or omit --validate-xml."
            )
            raise typer.Exit(code=2)

    # Determine absolute output path for exclusion logic (file target only).
    out_abs = output.resolve() if output.is_absolute() else (Path.cwd() / output).resolve()

    # Prepare ignore patterns
    user_ignore = list(ignore) if ignore else []

    # Auto-exclude output file to prevent self-inclusion loop (file output only).
    if not stdout and not clipboard and not stats_only:
        rel_out = try_relpath_posix(out_abs, root)
        if rel_out is not None:
            user_ignore.append("/" + rel_out)

    # Parse date filters
    newer_ts: Optional[float] = None
    if newer_than:
        newer_ts = _parse_datetime_arg(newer_than)
    older_ts: Optional[float] = None
    if older_than:
        older_ts = _parse_datetime_arg(older_than)

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

    # Dry-run handling: improved with tree output
    if dry_run:
        logger.info("Dry-run mode: showing filtered project tree.")
        try:
            entries = engine.filtered_scan()
            if entries:
                _build_tree(entries, console)
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
            _print_breakdown("Skipped by cause", stats.skipped_by_code, console)
            _print_breakdown("Errors by cause", stats.errors_by_code, console)

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