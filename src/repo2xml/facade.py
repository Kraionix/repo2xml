# src/repo2xml/facade.py
from __future__ import annotations

import io
import logging
import os
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO, List, Optional, Union

from repo2xml.contracts import ProgressReporter, ScanUseCase
from repo2xml.application.factories import ExportComponentFactory
from repo2xml.application.statistics_collector import StatisticsCollector
from repo2xml.application.filters import apply_file_filters
from repo2xml.application.scan_usecase_factory import ScanUseCaseFactory
from repo2xml.config import ExportConfig, RestoreConfig
from repo2xml.domain.exceptions import ConfigurationError, FacadeError
from repo2xml.domain.model import ExportStats, FileEntry, RestoreStats
from repo2xml.services.output.targets import OutputTarget

logger = logging.getLogger("repo2xml.facade")


@dataclass(slots=True)
class ExportComponents:
    """Container for components built during export pipeline setup."""
    orchestrator: PipelineOrchestrator
    collector: StatisticsCollector


class StreamTarget(OutputTarget):
    """
    OutputTarget that wraps an already opened binary stream.
    The stream is not closed by this target.
    """

    def __init__(self, stream: BinaryIO):
        self._stream = stream

    @contextmanager
    def open(self):
        yield self._stream

    def describe(self) -> str:
        return "user-provided stream"


class RepoXML:
    """Unified facade for export and restore operations."""

    def __init__(
        self,
        config: Union[ExportConfig, RestoreConfig],
        *,
        scan_usecase_factory: Optional[ScanUseCaseFactory] = None,
    ):
        self.config = config
        self._scan_usecase_factory = scan_usecase_factory or ScanUseCaseFactory()

    def export(
        self,
        root_path: Path,
        output_stream: BinaryIO,
        *,
        progress: Optional[ProgressReporter] = None,
        dry_run: bool = False,
        stats_only: bool = False,
    ) -> ExportStats:
        if not isinstance(self.config, ExportConfig):
            raise FacadeError("Export operation requires ExportConfig")

        config: ExportConfig = self.config
        # Validate configuration fully (structural + environment) before any I/O
        config.validate_all()

        root = root_path.resolve()
        self._validate_root_path(root)

        # Create ScanUseCase
        scan_use_case: ScanUseCase = self._scan_usecase_factory.create(
            config.scan, root, config.filter
        )

        output_target = StreamTarget(output_stream)
        factory = ExportComponentFactory(config, output_target, progress)
        orchestrator, collector = factory.build(scan_use_case=scan_use_case)

        try:
            stats = orchestrator.execute(root, stats_only=stats_only)
        except KeyboardInterrupt:
            raise
        except Exception as e:
            logger.exception("Export failed unexpectedly")
            raise FacadeError(f"Export failed: {e}") from e

        return stats

    def _validate_root_path(self, root: Path) -> None:
        if not root.is_dir():
            raise ConfigurationError(f"Root path is not a directory: {root}")
        if not os.access(root, os.R_OK):
            raise ConfigurationError(f"Root path is not readable: {root}")

    def filtered_scan(self, root_path: Path) -> List[FileEntry]:
        if not isinstance(self.config, ExportConfig):
            raise FacadeError("filtered_scan requires ExportConfig")
        config: ExportConfig = self.config
        root = root_path.resolve()

        # Use the ScanUseCase to get filtered and sorted entries
        scan_use_case = self._scan_usecase_factory.create(config.scan, root, config.filter)
        scan_result = scan_use_case.execute(root)
        return scan_result.entries

    def export_to_bytes(self, root_path: Path) -> bytes:
        buf = io.BytesIO()
        self.export(root_path, buf)
        return buf.getvalue()

    def restore(
        self,
        input_stream: BinaryIO,
        output_root: Path,
        *,
        progress: Optional[ProgressReporter] = None,
    ) -> RestoreStats:
        if not isinstance(self.config, RestoreConfig):
            raise FacadeError("Restore operation requires RestoreConfig")
        from repo2xml.application.restore_pipeline import RestorePipeline
        pipeline = RestorePipeline(self.config)
        reporter = progress or _null_reporter()
        return pipeline.execute(input_stream, output_root, reporter)

    def restore_from_path(self, xml_path: Path, output_root: Path) -> RestoreStats:
        with open(xml_path, "rb") as fh:
            return self.restore(fh, output_root)


Repo2XML = RepoXML


def _null_reporter() -> ProgressReporter:
    from repo2xml.application.progress import NullProgressReporter
    return NullProgressReporter()