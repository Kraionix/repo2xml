from __future__ import annotations

import io
import logging
from pathlib import Path
from typing import BinaryIO, Generator, Optional

from repo2xml.application.pipeline import ExportPipeline
from repo2xml.application.progress import NullProgressReporter, ProgressReporter
from repo2xml.config import Repo2XMLConfig
from repo2xml.domain.model import ExportStats, FileEntry
from repo2xml.services.ingest.ingestor import StandardIngestor
from repo2xml.services.scan.gitignore import GitignoreEngine
from repo2xml.services.scan.scanner import FileSystemScanner
from repo2xml.services.serialize.factories import create_serializer

logger = logging.getLogger("repo2xml.facade")


class Repo2XML:
    """
    High-level library facade for repo2xml.

    This object wires together:
      - scanner (filesystem + gitignore stack)
      - ingestor (safe reading + binary detection)
      - serializer (format-specific output writer)
      - pipeline (application orchestration)
    """

    def __init__(self, root_path: Path, config: Repo2XMLConfig):
        self.root_path = root_path.resolve()
        self.config = config

        # Normalize/validate config early.
        self.config.normalize()
        self.config.validate()

        self._gitignore_engine = GitignoreEngine(
            root_path=self.root_path,
            user_ignore=self.config.ignore_patterns,
            user_include=self.config.include_patterns,
        )

        self._scanner = FileSystemScanner(
            root=self.root_path,
            gitignore_engine=self._gitignore_engine,
            use_gitignore=self.config.use_gitignore,
            follow_symlinks_dirs=self.config.follow_symlinks_dirs,
            symlinks_files=self.config.symlinks_files.value,
            hard_exclude_dirs=set(self.config.hard_exclude_dirs),
        )

        self._ingestor = StandardIngestor(
            newline_mode=self.config.newline.value,
            use_ext_fastpath=self.config.binary_ext_fastpath,
            binary_ext_add=self.config.binary_ext_add,
            binary_ext_remove=self.config.binary_ext_remove,
        )

        self._serializer = create_serializer(
            fmt=self.config.format,
            formatting=self.config.formatting.value,
        )

        self._pipeline = ExportPipeline(
            root_path=self.root_path,
            config=self.config,
            scanner=self._scanner,
            ingestor=self._ingestor,
            serializer=self._serializer,
        )

    def scan(self) -> Generator[FileEntry, None, None]:
        """Yield file entries discovered in the repository (no content reads)."""
        yield from self._scanner.scan()

    def export(
        self,
        output_stream: BinaryIO,
        *,
        progress: Optional[ProgressReporter] = None,
    ) -> ExportStats:
        """
        Execute the full pipeline and write output bytes to output_stream.

        Args:
            output_stream: A writable binary stream (file, stdout, BytesIO).
            progress: Optional ProgressReporter (supports total + finish).

        Returns:
            ExportStats with per-run summary.
        """
        reporter = progress or NullProgressReporter()
        return self._pipeline.execute(output_stream=output_stream, progress=reporter)

    def export_to_bytes(self) -> bytes:
        """Convenience helper for programmatic usage (bytes only)."""
        buf = io.BytesIO()
        self.export(buf)
        return buf.getvalue()

    def export_to_bytes_with_stats(self) -> tuple[bytes, ExportStats]:
        """Convenience helper returning both bytes and stats."""
        buf = io.BytesIO()
        stats = self.export(buf)
        return buf.getvalue(), stats