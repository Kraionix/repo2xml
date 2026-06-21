# src/repo2xml/application/restore_pipeline.py
from __future__ import annotations

import logging
from pathlib import Path
from typing import BinaryIO

from repo2xml.application.contracts import ProgressReporter
from repo2xml.config import RestoreConfig
from repo2xml.domain.model import RestoreStats
from repo2xml.services.restore.restorer import FilesystemRestorer
from repo2xml.services.serialize.factory import get_format_factory

logger = logging.getLogger("repo2xml.restore_pipeline")


class RestorePipeline:
    def __init__(self, config: RestoreConfig):
        self.config = config
        factory = get_format_factory(config.format)
        self.deserializer = factory.create_deserializer()

    def execute(self, input_stream: BinaryIO, output_root: Path, progress: ProgressReporter) -> RestoreStats:
        progress.set_phase("Parsing")
        progress.set_total(None)
        repository = self.deserializer.parse(input_stream)
        progress.set_phase("Restoring")
        # The number of files isn't known until we consume, but we can provide an indeterminate bar.
        restorer = FilesystemRestorer(
            output_root,
            overwrite=self.config.overwrite,
            skip_existing=not self.config.overwrite,
            restore_mtime=self.config.restore_mtime,
            create_empty_for_missing=self.config.create_empty_for_missing,
        )
        stats = restorer.restore(repository.files)
        progress.set_total(stats.files_total)  # adjust for display
        progress.advance(stats.files_total)
        progress.finish()
        return stats