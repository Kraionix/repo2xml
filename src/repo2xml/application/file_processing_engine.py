# src/repo2xml/application/file_processing_engine.py
from __future__ import annotations

import logging
from typing import Iterable, Optional

from repo2xml.contracts import ProgressReporter
from repo2xml.application.entry_processor import EntryProcessor
from repo2xml.application.statistics_collector import StatisticsCollector
from repo2xml.application.writer_coordinator import WriterCoordinator
from repo2xml.domain.model import FileEntry

logger = logging.getLogger("repo2xml.file_processing_engine")


class FileProcessingEngine:
    """
    Processes a list of FileEntry objects sequentially.

    For each entry, it calls the EntryProcessor, updates statistics and
    progress, and (if write_enabled is True) writes the result via the
    WriterCoordinator.  Handles KeyboardInterrupt gracefully.
    """

    def __init__(
        self,
        entry_processor: EntryProcessor,
        writer_coordinator: Optional[WriterCoordinator],
        stats_collector: StatisticsCollector,
        progress: ProgressReporter,
        write_enabled: bool,
    ):
        self.entry_processor = entry_processor
        self.writer = writer_coordinator
        self.stats = stats_collector
        self.progress = progress
        self.write_enabled = write_enabled

    def process(self, entries: Iterable[FileEntry]) -> None:
        try:
            for entry in entries:
                self.progress.set_postfix(entry.name)
                result = self.entry_processor.process(entry)

                if result.status == "success":
                    self.stats.record_success(
                        token_count=result.token_count,
                        ext=entry.ext,
                    )
                    if self.write_enabled and self.writer is not None:
                        self.writer.write_file(
                            entry,
                            result.payload,
                            result.token_count,
                        )
                elif result.status == "skipped":
                    self.stats.record_skipped(
                        result.skip_code,
                        result.message,
                    )
                elif result.status == "error":
                    self.stats.record_error(
                        result.error_code,
                        result.message,
                    )
                else:
                    logger.warning("Unknown result status: %s", result.status)

                self.progress.advance(1)

        except KeyboardInterrupt:
            logger.warning("Interrupted during file processing.")
            raise