# src/repo2xml/facade.py
from __future__ import annotations

import io
import logging
from pathlib import Path
from typing import BinaryIO, List, Optional, Union

from repo2xml.application.contracts import IgnoreProvider, IngestorLike, ProgressReporter, ScannerLike
from repo2xml.application.export_pipeline import ExportPipeline
from repo2xml.application.filters import apply_file_filters
from repo2xml.application.restore_pipeline import RestorePipeline
from repo2xml.config import ExportConfig, RestoreConfig
from repo2xml.domain.exceptions import FacadeError, Repo2XMLError
from repo2xml.domain.model import ExportStats, FileEntry, RestoreStats
from repo2xml.services.ingest.ingestor import StandardIngestor
from repo2xml.services.scan.gitignore import GitignoreEngine
from repo2xml.services.scan.scanner import FileSystemScanner
from repo2xml.services.serialize.base import WriteFn
from repo2xml.services.serialize.factory import get_format_factory

logger = logging.getLogger("repo2xml.facade")


class RepoXML:
    """Unified facade for export and restore operations."""

    def __init__(self, config: Union[ExportConfig, RestoreConfig]):
        self.config = config

    # ---- Export API ----

    def export(
        self,
        root_path: Path,
        output_stream: BinaryIO,
        *,
        progress: Optional[ProgressReporter] = None,
    ) -> ExportStats:
        if not isinstance(self.config, ExportConfig):
            raise FacadeError("Export operation requires ExportConfig")
        config: ExportConfig = self.config
        root = root_path.resolve()

        # Build scanner and ingestor
        gitignore_engine: IgnoreProvider = GitignoreEngine(
            root_path=root,
            user_ignore=config.ignore_patterns,
            user_include=config.include_patterns,
        )
        scanner = FileSystemScanner(
            root=root,
            ignore_provider=gitignore_engine,
            use_gitignore=config.use_gitignore,
            follow_symlinks_dirs=config.follow_symlinks_dirs,
            symlinks_files=config.symlinks_files.value,
            hard_exclude_dirs=set(config.hard_exclude_dirs),
        )
        ingestor = StandardIngestor(
            newline_mode=config.newline.value,
            decode_errors=config.decode_errors.value,
            use_ext_fastpath=config.binary_ext_fastpath,
            binary_ext_add=config.binary_ext_add,
            binary_ext_remove=config.binary_ext_remove,
        )

        pipeline = ExportPipeline(
            root_path=root,
            config=config,
            scanner=scanner,
            ingestor=ingestor,
        )
        reporter = progress or _null_reporter()
        return pipeline.execute(output_stream=output_stream, progress=reporter)

    def filtered_scan(self, root_path: Path) -> List[FileEntry]:
        """Return a filtered list of FileEntry for dry-run display."""
        if not isinstance(self.config, ExportConfig):
            raise FacadeError("filtered_scan requires ExportConfig")
        config: ExportConfig = self.config
        root = root_path.resolve()
        gitignore_engine: IgnoreProvider = GitignoreEngine(
            root_path=root,
            user_ignore=config.ignore_patterns,
            user_include=config.include_patterns,
        )
        scanner = FileSystemScanner(
            root=root,
            ignore_provider=gitignore_engine,
            use_gitignore=config.use_gitignore,
            follow_symlinks_dirs=config.follow_symlinks_dirs,
            symlinks_files=config.symlinks_files.value,
            hard_exclude_dirs=set(config.hard_exclude_dirs),
        )
        entries = list(scanner.scan())
        entries = apply_file_filters(entries, config)
        entries.sort(key=lambda e: e.rel_path)
        return entries

    def export_to_bytes(self, root_path: Path) -> bytes:
        buf = io.BytesIO()
        self.export(root_path, buf)
        return buf.getvalue()

    # ---- Restore API ----

    def restore(
        self,
        input_stream: BinaryIO,
        output_root: Path,
        *,
        progress: Optional[ProgressReporter] = None,
    ) -> RestoreStats:
        if not isinstance(self.config, RestoreConfig):
            raise FacadeError("Restore operation requires RestoreConfig")
        pipeline = RestorePipeline(self.config)
        reporter = progress or _null_reporter()
        return pipeline.execute(input_stream, output_root, reporter)

    def restore_from_path(self, xml_path: Path, output_root: Path) -> RestoreStats:
        with open(xml_path, "rb") as fh:
            return self.restore(fh, output_root)


# Backward-compatible alias
Repo2XML = RepoXML


def _null_reporter() -> ProgressReporter:
    from repo2xml.application.progress import NullProgressReporter
    return NullProgressReporter()