# src/repo2xml/application/pipeline_orchestrator.py
from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

from repo2xml.contracts import ProgressReporter, ScannerLike
from repo2xml.application.entry_processor import EntryProcessor
from repo2xml.application.file_processing_engine import FileProcessingEngine
from repo2xml.application.scanner_service import ScannerService
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
        self.writer = writer_coordinator
        self.stats = statistics_collector
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

        scanner_service = ScannerService(self.scanner, self.config)
        scan_result = scanner_service.scan(self.root_path)
        entries = scan_result.entries
        warnings = scan_result.warnings

        if warnings:
            logger.warning("Scan warnings: %s", warnings)
            self.progress.set_warning_count(1)

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

        # ------------------------------------------------------------------
        # 3. Start writing (unless stats_only)
        # ------------------------------------------------------------------
        write_enabled = not stats_only

        # Enter the writer context – this ensures proper flushing/closing.
        with self.writer:
            if write_enabled:
                self.writer.write_header(meta)
                self.writer.write_structure(entries)

            # If mode is structure, we stop here (no file content).
            if self.config.mode == Mode.structure:
                if write_enabled:
                    self.writer.write_footer()
                self.progress.finish()
                return self.stats.get_export_stats(warnings)

            # Open the files section if we are writing and not in structure mode.
            if write_enabled:
                self.writer.write_files_open(self.config.mode.value)

            # ------------------------------------------------------------------
            # 4. Process files (only if there are entries)
            # ------------------------------------------------------------------
            if entries:
                engine = FileProcessingEngine(
                    entry_processor=self.entry_processor,
                    writer_coordinator=self.writer if write_enabled else None,
                    stats_collector=self.stats,
                    progress=self.progress,
                    write_enabled=write_enabled,
                )

                try:
                    engine.process(entries)
                except KeyboardInterrupt:
                    logger.warning("Export interrupted by user. Finishing partial document.")
                    raise

            # ------------------------------------------------------------------
            # 5. Finish the document (unless stats_only)
            # ------------------------------------------------------------------
            if write_enabled:
                self.writer.write_files_close()
                token_stats = self.stats.get_export_stats(warnings).token_stats
                self.writer.write_statistics(token_stats)
                self.writer.write_footer()

        # ------------------------------------------------------------------
        # 6. Finalise
        # ------------------------------------------------------------------
        self.progress.finish()
        return self.stats.get_export_stats(warnings)