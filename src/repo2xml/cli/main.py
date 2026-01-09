from __future__ import annotations

import io
from pathlib import Path
from typing import List, Optional

import pyperclip
import typer

from repo2xml.application.progress import NullProgressReporter, TqdmProgressReporter
from repo2xml.config import (
    BinaryMode,
    Formatting,
    Mode,
    NewlineMode,
    Repo2XMLConfig,
    RootPathMode,
    SymlinkFilesMode,
)
from repo2xml.cli.ui import LogLevel, setup_logging
from repo2xml.facade import Repo2XML
from repo2xml.services.ingest.redact import redact_secrets
from repo2xml.services.output.targets import CompressMode, open_output_stream
from repo2xml.utils.paths import try_relpath_posix

app = typer.Typer(add_completion=False)


def _print_breakdown(title: str, data: dict[str, int]) -> None:
    if not data:
        return
    typer.echo(title)
    for k, v in sorted(data.items(), key=lambda kv: (-kv[1], kv[0])):
        typer.echo(f"  - {k}: {v}")


@app.callback(invoke_without_command=True)
def main(
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
        help="Output path (ignored if --stdout or --clipboard).",
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
        help="Do not write output. Only list files that would be processed.",
    ),
    progress: bool = typer.Option(
        True,
        "--progress/--no-progress",
        help="Show progress bars (default: progress).",
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
) -> None:
    """
    repo2xml: convert a repository into a single context document for LLM ingestion.
    """
    logger = setup_logging(log_level)
    root = path.resolve()

    # Determine absolute output path for exclusion logic
    out_abs = output.resolve() if output.is_absolute() else (Path.cwd() / output).resolve()

    # Prepare ignore patterns
    user_ignore = list(ignore) if ignore else []

    # Auto-exclude output file to prevent self-inclusion loop.
    if not stdout and not clipboard:
        rel_out = try_relpath_posix(out_abs, root)
        if rel_out:
            user_ignore.append("/" + rel_out)
        else:
            user_ignore.append(out_abs.name)

    processors = []
    if redact:
        processors.append(redact_secrets)

    config = Repo2XMLConfig(
        format="xml",
        mode=mode,
        formatting=formatting,
        binary=binary,
        newline=newline,
        include_timestamp=not no_timestamp,
        root_path_mode=root_path_mode,
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
        # Hashing is allowed beyond --max-size by default (0 = unlimited).
        max_hash_size=0,
        report=report,
        text_processors=processors,
    )

    engine = Repo2XML(root, config)

    # Dry-run handling
    if dry_run:
        logger.info("Dry-run mode: Listing files only.")
        try:
            for entry in engine.scan():
                print(entry.rel_path)
        except KeyboardInterrupt:
            logger.warning("Interrupted.")
            raise typer.Exit(code=130)
        return

    # Clipboard Mode
    if clipboard:
        logger.info("Mode: Clipboard. Buffering output...")
        mem_buffer = io.BytesIO()

        try:
            reporter = TqdmProgressReporter() if progress else NullProgressReporter()
            stats = engine.export(mem_buffer, progress=reporter)

            xml_content = mem_buffer.getvalue().decode("utf-8")
            pyperclip.copy(xml_content)

            logger.info("Success! Context copied to clipboard (%d chars).", len(xml_content))
            logger.info(
                "Stats: total=%d, emitted=%d, skipped=%d, errors=%d",
                stats.files_total,
                stats.files_emitted,
                stats.files_skipped,
                stats.files_errors,
            )

            if report:
                _print_breakdown("Skipped by cause:", stats.skipped_by_code)
                _print_breakdown("Errors by cause:", stats.errors_by_code)

        except pyperclip.PyperclipException as e:
            logger.error("Clipboard error: %s", e)
            logger.error("On Linux, ensure xclip or xsel is installed.")
            raise typer.Exit(code=1)
        except Exception as e:
            logger.error("Fatal error during clipboard export: %s", e)
            raise typer.Exit(code=1)
        return

    # File / Stdout Mode
    try:
        out_stream, closer = open_output_stream(
            output_path=out_abs,
            use_stdout=stdout,
            compress=compress,
        )
    except ImportError:
        typer.secho("zstd compression requires: pip install zstandard", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=2)

    try:
        reporter = TqdmProgressReporter() if progress else None
        stats = engine.export(out_stream, progress=reporter)

        if not stdout:
            logger.info("Done. Output written to: %s", out_abs)

        logger.info(
            "Stats: total=%d, emitted=%d, skipped=%d, errors=%d",
            stats.files_total,
            stats.files_emitted,
            stats.files_skipped,
            stats.files_errors,
        )
        if stats.scan_warning_summary:
            logger.warning("Scan warnings: %s", stats.scan_warning_summary)

        if report:
            _print_breakdown("Skipped by cause:", stats.skipped_by_code)
            _print_breakdown("Errors by cause:", stats.errors_by_code)

    except KeyboardInterrupt:
        logger.warning("Interrupted.")
        raise typer.Exit(code=130)
    except Exception as e:
        logger.error("Fatal error: %s", e)
        raise typer.Exit(code=1)
    finally:
        try:
            closer()
        except Exception:
            pass