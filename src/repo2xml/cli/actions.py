# src/repo2xml/cli/actions.py (сокращённо)
from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console

from repo2xml.application.progress import NullProgressReporter, RichProgressReporter
from repo2xml.cli.reporting import print_breakdown
from repo2xml.config import ExportConfig, RestoreConfig
from repo2xml.facade import RepoXML
from repo2xml.services.output.targets import ...

logger = logging.getLogger("repo2xml.cli")

def execute_export(...):
    # как раньше, но использует ExportConfig и RepoXML.export
    ...

def execute_restore(
    console: Console,
    xml_file: Path,
    output: Path,
    overwrite: bool,
    restore_mtime: bool,
    create_empty: bool,
    report: bool,
):
    config = RestoreConfig(
        overwrite=overwrite,
        restore_mtime=restore_mtime,
        create_empty_for_missing=create_empty,
    )
    config.normalize()
    config.validate()
    engine = RepoXML(config)
    start = time.time()
    try:
        with open(xml_file, "rb") as fh:
            stats = engine.restore(fh, output, progress=RichProgressReporter())
    except Exception as e:
        logger.error("Restore failed: %s", e)
        raise typer.Exit(code=1)
    elapsed = time.time() - start
    logger.info("Restore completed in %.2f s", elapsed)
    logger.info(
        "Stats: total=%d, created=%d, skipped=%d, errors=%d, dirs=%d, symlinks=%d",
        stats.files_total, stats.files_created, stats.files_skipped,
        stats.files_errors, stats.dirs_created, stats.symlinks_created,
    )
    if report:
        print_breakdown("Skipped by cause", stats.skipped_by_code, console)
        print_breakdown("Errors by cause", stats.errors_by_code, console)