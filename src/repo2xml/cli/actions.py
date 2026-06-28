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
from repo2xml.cli.reporting import build_tree, print_breakdown
from repo2xml.cli.ui import LogLevel
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
    RestoreConfig,
    RootPathMode,
    ScanConfig,
    SymlinkFilesMode,
    TextHandlingConfig,
    TokenCountConfig,
)
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


def execute_export(
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
    ignore: Optional[list[str]],
    include: Optional[list[str]],
    hard_exclude: list[str],
    follow_symlinks_dirs: bool,
    symlinks_files: SymlinkFilesMode,
    max_size: int,
    binary: BinaryMode,
    newline: NewlineMode,
    decode_errors: DecodeErrors,
    source: str,
    source_option: Optional[list[str]],
    redact_config: Optional[Path],
    classify_config: Optional[Path],
    count_tokens: bool,
    tokenizer_model: str,
) -> None:
    """Run the full repo2xml export workflow."""
    if version:
        typer.echo(f"repo2xml {tool_version('repo2xml')}")
        raise typer.Exit(code=0)

    if quiet:
        progress = False
        log_level = LogLevel.error

    root = path.resolve()

    # Disable token counting in dry-run or stats-only modes
    if dry_run or stats_only:
        count_tokens = False

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

    source_opts = {}
    if source_option:
        for item in source_option:
            if "=" not in item:
                raise typer.BadParameter(
                    f"Source option must be in key=value format: '{item}'"
                )
            key, _, value = item.partition("=")
            source_opts[key.strip()] = value.strip()

    try:
        scan = ScanConfig(
            use_gitignore=gitignore,
            ignore_patterns=user_ignore,
            include_patterns=list(include) if include else [],
            hard_exclude_dirs=hard_exclude,
            follow_symlinks_dirs=follow_symlinks_dirs,
            symlinks_files=symlinks_files,
            source=source,
            source_options=source_opts,
        )
        filter_ = FilterConfig(
            min_file_size=size_min,
            max_file_size=size_max,
            newer_than=newer_ts,
            older_than=older_ts,
        )
        output_format = OutputFormatConfig(
            formatting=formatting,
            include_timestamp=not no_timestamp,
            include_mtime=not no_mtime,
            include_size=not no_size,
            root_path_mode=root_path_mode,
        )
        binary_cfg = BinaryHandlingConfig(
            mode=binary,
            max_base64_size=max_size,
            max_hash_size=0,
        )
        text_cfg = TextHandlingConfig(
            max_text_size=max_size,
            newline=newline,
            decode_errors=decode_errors,
        )
        redact_cfg = RedactConfig(
            enabled=redact,
            config_path=redact_config,
        )
        classify_cfg = ClassifyConfig(
            config_path=classify_config,
        )
        token_cfg = TokenCountConfig(
            enabled=count_tokens,
            model=tokenizer_model,
        )

        config = ExportConfig(
            mode=mode,
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
    except ConfigurationError as e:
        logger.error("Configuration error: %s", e)
        raise typer.Exit(code=2)

    engine = RepoXML(config)

    if dry_run:
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
            stats = engine.export(
                root,
                out_stream,
                progress=reporter,
                dry_run=dry_run,
                stats_only=stats_only,
            )

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

        # Token statistics output (always shown if available, unless quiet)
        if stats.token_stats is not None and not quiet:
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

            if report and ts.tokens_by_extension:
                ext_table = Table(title="Tokens by Extension", show_header=True, header_style="bold")
                ext_table.add_column("Extension", style="dim")
                ext_table.add_column("Tokens", justify="right")
                ext_table.add_column("Percentage", justify="right")
                total = ts.total_tokens
                for ext, count in sorted(ts.tokens_by_extension.items(), key=lambda x: -x[1]):
                    pct = f"{count / total * 100:.1f}%" if total > 0 else "0%"
                    ext_table.add_row(ext or "(no extension)", f"{count:,}", pct)
                console.print(ext_table)

        if validate_xml:
            xml_path = out_abs
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
    strict_validation: bool = True,
) -> None:
    """Run the restore workflow."""
    config = RestoreConfig(
        overwrite=overwrite,
        restore_mtime=restore_mtime,
        create_empty_for_missing=create_empty,
        strict_validation=strict_validation,
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