# src/repo2xml/cli/actions.py
from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

from repo2xml.application.progress import NullProgressReporter, RichProgressReporter
from repo2xml.cli.options import ExportOptions
from repo2xml.cli.reporting import build_tree, print_breakdown, print_scan_error_breakdown
from repo2xml.cli.ui import LogLevel
from repo2xml.config import RestoreConfig
from repo2xml.domain.exceptions import (
    ConfigurationError,
    OutputError,
    Repo2XMLError,
    SerializationError,
)
from repo2xml.facade import RepoXML
from repo2xml.services.output.targets import (
    ClipboardTarget,
    CompressMode,
    DevNullTarget,
    FileTarget,
    OutputTarget,
    StdoutTarget,
)
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


def execute_export(
    *,
    console: Console,
    options: ExportOptions,
) -> None:
    """Run the full repo2xml export workflow using options object."""
    # Map log level
    from repo2xml.cli.ui import LogLevel
    log_level_map = {"info": LogLevel.info, "warning": LogLevel.warning, "error": LogLevel.error}
    log_level = log_level_map.get(options.log_level, LogLevel.info)

    root = options.path.resolve()

    # Disable token counting in dry-run or stats-only modes
    if options.dry_run or options.stats_only:
        options.count_tokens = False

    # Validate compatibility of options
    try:
        options.validate_export_compatibility()
    except ConfigurationError as e:
        logger.error("Configuration error: %s", e)
        raise typer.Exit(code=2)

    # Build ExportConfig
    try:
        config = options.build_config(root)
    except ConfigurationError as e:
        logger.error("Configuration error: %s", e)
        raise typer.Exit(code=2)

    engine = RepoXML(config)

    # Dry-run
    if options.dry_run:
        logger.info("Dry-run mode: showing filtered project tree.")
        try:
            entries = engine.filtered_scan(root)
            if entries:
                build_tree(entries, console)
            else:
                console.print("[yellow]No files matched the given filters.[/yellow]")
        except KeyboardInterrupt:
            logger.warning("Interrupted.")
            raise typer.Exit(code=130)
        return

    target = _select_target(
        stdout=options.stdout,
        clipboard=options.clipboard,
        stats_only=options.stats_only,
        output_path=options.output.resolve() if options.output.is_absolute() else (Path.cwd() / options.output).resolve(),
        compress=options.compress,
    )

    reporter = RichProgressReporter(no_color=options.no_color) if options.progress else NullProgressReporter()

    start_time = time.time()
    try:
        with target.open() as out_stream:
            stats = engine.export(
                root,
                out_stream,
                progress=reporter,
                dry_run=options.dry_run,
                stats_only=options.stats_only,
            )

        elapsed = time.time() - start_time

        if options.stats_only:
            logger.info("Done. Output discarded (%s).", target.describe())
        elif options.stdout:
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

        # Reports
        if options.report:
            print_breakdown("Skipped by cause", stats.skipped_by_code, console)
            print_breakdown("Errors by cause", stats.errors_by_code, console)

            if stats.scan_stats:
                print_scan_error_breakdown(stats.scan_stats, console, verbose=options.verbose_errors)

            if stats.redaction_stats:
                rs = stats.redaction_stats
                table = Table(title="Redaction Statistics", show_header=True, header_style="bold")
                table.add_column("Metric", style="dim")
                table.add_column("Value", justify="right")
                table.add_row("Files processed", str(rs.total_files_processed))
                table.add_row("Files skipped", str(rs.total_files_skipped))
                table.add_row("Total matches", str(rs.total_matches))
                if rs.matches_by_rule:
                    table.add_section()
                    table.add_row("Matches by rule", "")
                    for rule_name, count in sorted(rs.matches_by_rule.items(), key=lambda x: -x[1]):
                        table.add_row(f"  {rule_name}", str(count))
                console.print(table)

            if stats.classification_stats:
                cs = stats.classification_stats
                table = Table(title="Classification Statistics", show_header=True, header_style="bold")
                table.add_column("Metric", style="dim")
                table.add_column("Value", justify="right")
                table.add_row("Total files", str(cs.total_files))
                table.add_row("By extension", str(cs.by_extension))
                table.add_row("By content analysis", str(cs.by_content))
                if cs.errors:
                    table.add_row("Errors", str(cs.errors))
                console.print(table)

        # Token statistics
        if stats.token_stats is not None and not options.quiet:
            ts = stats.token_stats
            token_table = Table(title="Token Statistics", show_header=True, header_style="bold")
            token_table.add_column("Metric", style="dim")
            token_table.add_column("Value", justify="right")
            token_table.add_row("Total tokens", f"{ts.total_tokens:,}")
            token_table.add_row("Files processed", str(ts.files_processed))
            token_table.add_row("Files skipped (errors)", str(ts.files_skipped))
            token_table.add_row("Max tokens in file", f"{ts.max_tokens:,}")
            token_table.add_row("Min tokens in file", f"{ts.min_tokens:,}")
            token_table.add_row("Errors during tokenization", str(ts.errors))
            console.print(token_table)

            if options.report and ts.tokens_by_extension:
                ext_table = Table(title="Tokens by Extension", show_header=True, header_style="bold")
                ext_table.add_column("Extension", style="dim")
                ext_table.add_column("Tokens", justify="right")
                ext_table.add_column("Percentage", justify="right")
                total = ts.total_tokens
                for ext, count in sorted(ts.tokens_by_extension.items(), key=lambda x: -x[1]):
                    pct = f"{count / total * 100:.1f}%" if total > 0 else "0%"
                    ext_table.add_row(ext or "(no extension)", f"{count:,}", pct)
                console.print(ext_table)

        if options.validate_xml:
            xml_path = options.output.resolve() if options.output.is_absolute() else (Path.cwd() / options.output).resolve()
            try:
                import xml.etree.ElementTree as ET
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


def execute_restore(
    console: Console,
    xml_file: Path,
    output: Path,
    overwrite: bool,
    restore_mtime: bool,
    create_empty: bool,
    report: bool,
    allow_absolute_symlinks: bool = False,
    strict_validation: bool = True,
    verbose_errors: bool = False,
) -> None:
    """Run the restore workflow."""
    # Warn if absolute symlinks are allowed.
    if allow_absolute_symlinks:
        console.print(
            "[bold yellow]⚠️  WARNING: --allow-absolute-symlinks is enabled.[/bold yellow]"
        )
        console.print(
            "[yellow]   Absolute symlinks can point outside the output root and pose a security risk.[/yellow]"
        )
        console.print(
            "[yellow]   Ensure you trust the source of the XML file.[/yellow]"
        )

    output_root = output.resolve()
    if output_root.exists() and not output_root.is_dir():
        logger.error("Output path exists and is not a directory: %s", output_root)
        raise typer.Exit(code=2)

    config = RestoreConfig(
        overwrite=overwrite,
        restore_mtime=restore_mtime,
        create_empty_for_missing=create_empty,
        strict_validation=strict_validation,
        allow_absolute_symlinks=allow_absolute_symlinks,
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