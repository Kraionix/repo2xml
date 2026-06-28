# src/repo2xml/facade.py
from __future__ import annotations

import io
import logging
import os
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO, List, Optional, Union

from repo2xml.application.contracts import ProgressReporter
from repo2xml.application.factories import ExportComponentFactory
from repo2xml.application.statistics_collector import StatisticsCollector
from repo2xml.application.filters import apply_file_filters
from repo2xml.config import ExportConfig, RestoreConfig
from repo2xml.domain.exceptions import ConfigurationError, FacadeError
from repo2xml.domain.model import ExportStats, FileEntry, RestoreStats
from repo2xml.services.scan.gitignore import GitignoreEngine
from repo2xml.services.scan.registry import create_scanner
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

    def __init__(self, config: Union[ExportConfig, RestoreConfig]):
        self.config = config

    def export(
        self,
        root_path: Path,
        output_stream: BinaryIO,
        *,
        progress: Optional[ProgressReporter] = None,
        dry_run: bool = False,
        stats_only: bool = False,
    ) -> ExportStats:
        """Export a repository to the given output stream."""
        if not isinstance(self.config, ExportConfig):
            raise FacadeError("Export operation requires ExportConfig")

        config: ExportConfig = self.config

        # ------------------------------------------------------------------
        # 1. Pre-flight validation
        # ------------------------------------------------------------------
        root = root_path.resolve()
        self._validate_root_path(root)
        self._validate_dependencies(config)

        # ------------------------------------------------------------------
        # 2. Build all components via factory
        # ------------------------------------------------------------------
        output_target = StreamTarget(output_stream)
        factory = ExportComponentFactory(config, root, output_target, progress)
        orchestrator, collector = factory.build()

        # ------------------------------------------------------------------
        # 3. Run the pipeline
        # ------------------------------------------------------------------
        try:
            stats = orchestrator.execute(stats_only=stats_only)
        except KeyboardInterrupt:
            raise
        except Exception as e:
            logger.exception("Export failed unexpectedly")
            raise FacadeError(f"Export failed: {e}") from e

        return stats

    # ------------------------------------------------------------------
    # Private helper methods
    # ------------------------------------------------------------------

    def _validate_root_path(self, root: Path) -> None:
        """Check that root exists and is readable."""
        if not root.is_dir():
            raise ConfigurationError(f"Root path is not a directory: {root}")
        if not os.access(root, os.R_OK):
            raise ConfigurationError(f"Root path is not readable: {root}")

    def _validate_dependencies(self, config: ExportConfig) -> None:
        """Check optional dependencies if their features are enabled."""
        if config.token.enabled:
            try:
                import transformers  # noqa: F401
            except ImportError:
                raise ConfigurationError(
                    "Token counting requires the 'transformers' library. "
                    "Install with: pip install repo2xml[tokens]"
                )

    # ------------------------------------------------------------------
    # Other public methods
    # ------------------------------------------------------------------

    def filtered_scan(self, root_path: Path) -> List[FileEntry]:
        """Return filtered list of files without performing a full export."""
        if not isinstance(self.config, ExportConfig):
            raise FacadeError("filtered_scan requires ExportConfig")
        config: ExportConfig = self.config
        root = root_path.resolve()

        gitignore_engine = GitignoreEngine(
            root_path=root,
            user_ignore=config.scan.ignore_patterns,
            user_include=config.scan.include_patterns,
        )

        scanner = create_scanner(
            config.scan.source,
            root_path=root,
            ignore_provider=gitignore_engine,
            use_gitignore=config.scan.use_gitignore,
            follow_symlinks_dirs=config.scan.follow_symlinks_dirs,
            symlinks_files=config.scan.symlinks_files.value,
            hard_exclude_dirs=set(config.scan.hard_exclude_dirs),
            **config.scan.source_options,
        )

        entries = list(scanner.scan())
        entries = apply_file_filters(entries, config)
        entries.sort(key=lambda e: e.rel_path)
        return entries

    def export_to_bytes(self, root_path: Path) -> bytes:
        """Export the repository to an in-memory bytes buffer."""
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
        """Restore a repository from an XML stream."""
        if not isinstance(self.config, RestoreConfig):
            raise FacadeError("Restore operation requires RestoreConfig")
        from repo2xml.application.restore_pipeline import RestorePipeline
        pipeline = RestorePipeline(self.config)
        reporter = progress or _null_reporter()
        return pipeline.execute(input_stream, output_root, reporter)

    def restore_from_path(self, xml_path: Path, output_root: Path) -> RestoreStats:
        """Restore a repository from an XML file."""
        with open(xml_path, "rb") as fh:
            return self.restore(fh, output_root)


# Alias for backward compatibility
Repo2XML = RepoXML


def _null_reporter() -> ProgressReporter:
    from repo2xml.application.progress import NullProgressReporter
    return NullProgressReporter()