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

# ---- Export (default command) ----
@app.callback(invoke_without_command=True)
def main(
    # ... все старые параметры экспорта
    # для краткости опущены, но они точно такие же, как раньше,
    # только теперь вызывают execute_export
):
    """repo2xml: convert a repository into a single context document for LLM ingestion."""
    ...


# ---- Restore subcommand ----
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
):
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