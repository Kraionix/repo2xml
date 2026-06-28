# src/repo2xml/application/pipeline_orchestrator.py
from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

from repo2xml.application.contracts import ProgressReporter, ScannerLike
from repo2xml.application.entry_processor import EntryProcessor
from repo2xml.application.filters import apply_file_filters
from repo2xml.application.statistics_collector import StatisticsCollector
from repo2xml.application.writer_coordinator import WriterCoordinator
from repo2xml.config import ExportConfig, Mode
from repo2xml.domain.constants import SCHEMA_VERSION
from repo2xml.domain.model import ExportMeta, ExportStats, FileEntry
from repo2xml.utils.paths import format_root_path
from repo2xml.utils.version import tool_version

logger = logging.getLogger("repo2xml.pipeline_orchestrator")


class PipelineOrchestrator:
    """
    Orchestrates the entire export pipeline.

    Coordinates scanning, filtering, processing of each file,
    writing via WriterCoordinator, and statistics collection.
    """

    def __init__(
        self,
        config: ExportConfig,
        scanner: ScannerLike,
        entry_processor: EntryProcessor,
        writer_coordinator: WriterCoordinator,
        statistics_collector: StatisticsCollector,
        progress_reporter: ProgressReporter,
        root_path: Path,
    ):
        self.config = config
        self.scanner = scanner
        self.entry_processor = entry_processor
        self.writer_coordinator = writer_coordinator
        self.statistics_collector = statistics_collector
        self.progress = progress_reporter
        self.root_path = root_path

    def execute(self, *, stats_only: bool = False) -> ExportStats:
        """
        Run the full export pipeline.

        Args:
            stats_only: If True, only collect statistics, do not write output.

        Returns:
            ExportStats with aggregated results.
        """
        # ------------------------------------------------------------------
        # 1. Scan and filter
        # ------------------------------------------------------------------
        self.progress.set_phase("Scanning")
        self.progress.set_total(None)
        logger.info("Scanning repository: %s", self.root_path)

        entries: List[FileEntry] = []
        for entry in self.scanner.scan():
            entries.append(entry)
            self.progress.advance(1)

        original_count = len(entries)
        entries = apply_file_filters(entries, self.config.filter)
        if len(entries) != original_count:
            logger.info(
                "File-level filters removed %d entries (%d remaining).",
                original_count - len(entries),
                len(entries),
            )

        # Gather scan warnings (if any)
        scan_warn: Optional[str] = None
        if self.scanner.stats is not None and self.scanner.stats.has_issues():
            scan_warn = self.scanner.stats.summary()
            logger.warning("Scan warnings: %s", scan_warn)
            total_warnings = sum(
                getattr(self.scanner.stats, attr, 0)
                for attr in (
                    "dirs_scandir_errors",
                    "entry_is_symlink_errors",
                    "entry_is_dir_errors",
                    "entry_is_file_errors",
                    "entry_stat_errors",
                    "entry_readlink_errors",
                )
            )
            self.progress.set_warning_count(total_warnings)

        total = len(entries)
        logger.info("Found %d files.", total)
        self.progress.set_total(total)
        self.progress.set_phase("Processing")

        # ------------------------------------------------------------------
        # 2. Prepare meta and write header / structure (skip if stats_only)
        # ------------------------------------------------------------------
        generated_at = None
        if self.config.output.include_timestamp:
            generated_at = datetime.now(timezone.utc).isoformat()

        meta = ExportMeta(
            root_path=format_root_path(self.root_path, self.config.output.root_path_mode),
            generated_at_utc=generated_at,
            tool_version=tool_version("repo2xml"),
            schema_version=SCHEMA_VERSION,
        )

        with self.writer_coordinator:
            if not stats_only:
                self.writer_coordinator.write_header(meta)
                self.writer_coordinator.write_structure(entries)

            if self.config.mode == Mode.structure and not stats_only:
                self.writer_coordinator.write_footer()
                self.progress.finish()
                return self.statistics_collector.get_export_stats(scan_warn)

            if not stats_only:
                self.writer_coordinator.write_files_open(self.config.mode.value)

            # ------------------------------------------------------------------
            # 3. Process each file
            # ------------------------------------------------------------------
            try:
                for entry in entries:
                    result = self.entry_processor.process(entry)

                    if result.status == "success":
                        self.statistics_collector.record_success(
                            token_count=result.token_count,
                            ext=entry.ext,
                        )
                        if not stats_only:
                            self.writer_coordinator.write_file(
                                entry,
                                result.payload,
                                result.token_count,
                            )
                    elif result.status == "skipped":
                        self.statistics_collector.record_skipped(
                            result.skip_code,
                            result.message,
                        )
                    elif result.status == "error":
                        self.statistics_collector.record_error(
                            result.error_code,
                            result.message,
                        )
                    else:
                        logger.warning("Unknown result status: %s", result.status)

                    self.progress.set_postfix(entry.name)
                    self.progress.advance(1)

            except KeyboardInterrupt:
                logger.warning("Interrupted by user. Closing writer and generating partial statistics.")
                if not stats_only:
                    self.writer_coordinator.close()
                self.progress.finish()
                raise

            # ------------------------------------------------------------------
            # 4. Write statistics and footer (skip if stats_only)
            # ------------------------------------------------------------------
            if not stats_only:
                self.writer_coordinator.write_files_close()
                token_stats = self.statistics_collector.get_export_stats(scan_warn).token_stats
                self.writer_coordinator.write_statistics(token_stats)
                self.writer_coordinator.write_footer()

        self.progress.finish()
        final_stats = self.statistics_collector.get_export_stats(scan_warn)
        return final_stats