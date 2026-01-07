from __future__ import annotations

import gzip
import sys
import io
import pyperclip
from enum import Enum
from pathlib import Path
from typing import BinaryIO, Callable, List, Optional

import typer
from tqdm import tqdm

from repo2xml.api import Repo2XML
from repo2xml.config import (
    BinaryMode,
    Formatting,
    Mode,
    NewlineMode,
    Repo2XMLConfig,
    SymlinkFilesMode,
)
from repo2xml.cli.ui import LogLevel, setup_logging

app = typer.Typer(add_completion=False)


class CompressMode(str, Enum):
    """Output compression for the whole XML stream."""
    none = "none"
    gzip = "gzip"
    zstd = "zstd"


def _open_output_stream(
    *,
    output_path: Path,
    use_stdout: bool,
    compress: CompressMode,
) -> tuple[BinaryIO, Callable[[], None]]:
    """
    Open an output stream for the XML bytes.
    Handles File vs Stdout and Compression transparently.

    Returns: (binary_stream, closer_callback)
    """
    if use_stdout:
        base: BinaryIO = sys.stdout.buffer
        if compress == CompressMode.none:
            return base, lambda: None

        if compress == CompressMode.gzip:
            gz = gzip.GzipFile(fileobj=base, mode="wb")
            return gz, gz.close

        if compress == CompressMode.zstd:
            import zstandard as zstd  # type: ignore
            cctx = zstd.ZstdCompressor(level=3)
            zw = cctx.stream_writer(base)
            return zw, zw.close

    # File output
    output_path.parent.mkdir(parents=True, exist_ok=True)
    raw = open(output_path, "wb")

    if compress == CompressMode.none:
        return raw, raw.close

    if compress == CompressMode.gzip:
        gz = gzip.GzipFile(fileobj=raw, mode="wb")
        return gz, lambda: (gz.close(), raw.close())

    if compress == CompressMode.zstd:
        import zstandard as zstd  # type: ignore
        cctx = zstd.ZstdCompressor(level=3)
        zw = cctx.stream_writer(raw)
        return zw, lambda: (zw.close(), raw.close())

    return raw, raw.close


def _try_relpath(child: Path, root: Path) -> Optional[str]:
    """Return POSIX relative path if child is inside root, else None."""
    try:
        return child.resolve().relative_to(root.resolve()).as_posix()
    except Exception:
        return None


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
        help="XML formatting.",
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
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Do not write XML. Only list files that would be processed.",
    ),
    progress: bool = typer.Option(
        True,
        "--progress/--no-progress",
        help="Show progress bars (default: progress).",
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
        help="Max file size in bytes to include content for (larger files are skipped).",
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
    repo2xml: convert a repository into a single XML context for LLM ingestion.
    """
    logger = setup_logging(log_level)
    root = path.resolve()

    # Determine absolute output path for exclusion logic
    out_abs = output.resolve() if output.is_absolute() else (Path.cwd() / output).resolve()

    # Prepare configuration
    user_ignore = list(ignore) if ignore else []

    # Auto-exclude output file to prevent self-inclusion loop.
    # If the output is inside the scanned root, anchor it to repo root ("/...") so we do not
    # accidentally ignore other same-named files elsewhere in the tree.
    if not stdout and not clipboard:
        rel_out = _try_relpath(out_abs, root)
        if rel_out:
            user_ignore.append("/" + rel_out)
        else:
            user_ignore.append(out_abs.name)

    config = Repo2XMLConfig(
        mode=mode,
        formatting=formatting,
        binary=binary,
        newline=newline,
        include_timestamp=not no_timestamp,
        use_gitignore=gitignore,
        ignore_patterns=user_ignore,
        include_patterns=list(include) if include else [],
        hard_exclude_dirs=hard_exclude,
        follow_symlinks_dirs=follow_symlinks_dirs,
        symlinks_files=symlinks_files,
        max_file_size=max_size,
    )

    engine = Repo2XML(root, config)

    # Dry-run handling
    if dry_run:
        logger.info("Dry-run mode: Listing files only.")
        try:
            for node in engine.scan():
                print(node.rel_path)
        except KeyboardInterrupt:
            logger.warning("Interrupted.")
            raise typer.Exit(code=130)
        return

    # 1. Clipboard Mode
    if clipboard:
        logger.info("Mode: Clipboard. Buffering output...")
        mem_buffer = io.BytesIO()

        try:
            if progress:
                with tqdm(desc="Processing", unit="file") as pbar:
                    engine.export(mem_buffer, progress_callback=lambda n: pbar.update(n))
            else:
                engine.export(mem_buffer)

            # Decode (XML is text) and copy
            xml_content = mem_buffer.getvalue().decode("utf-8")
            pyperclip.copy(xml_content)
            logger.info("Success! XML context copied to clipboard (%d chars).", len(xml_content))

        except pyperclip.PyperclipException as e:
            logger.error("Clipboard error: %s", e)
            logger.error("On Linux, ensure xclip or xsel is installed.")
            raise typer.Exit(code=1)
        except Exception as e:
            logger.error("Fatal error during clipboard export: %s", e)
            raise typer.Exit(code=1)
        return

    # 2. Standard File / Stdout Mode
    try:
        out_stream, closer = _open_output_stream(
            output_path=out_abs,
            use_stdout=stdout,
            compress=compress,
        )
    except ImportError:
        typer.secho("zstd compression requires: pip install zstandard", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=2)

    try:
        if progress:
            # Wrap progress callback
            with tqdm(desc="Processing", unit="file") as pbar:
                engine.export(out_stream, progress_callback=lambda n: pbar.update(n))
        else:
            engine.export(out_stream)

        if not stdout:
            logger.info("Done. Output written to: %s", out_abs)

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