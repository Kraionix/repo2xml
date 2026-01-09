from __future__ import annotations

import io
import logging
from pathlib import Path
from typing import BinaryIO, Callable, Generator, Optional

from repo2xml.application.pipeline import ExportPipeline
from repo2xml.application.progress import CallbackProgressReporter, NullProgressReporter, ProgressReporter
from repo2xml.config import Repo2XMLConfig
from repo2xml.domain.model import FileEntry
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
            max_size=self.config.max_file_size,
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
        progress_callback: Optional[Callable[[int], None]] = None,
    ) -> None:
        """
        Execute the full pipeline and write output bytes to output_stream.

        output_stream must be a writable binary stream.
        """
        reporter: ProgressReporter
        if progress_callback is not None:
            reporter = CallbackProgressReporter(progress_callback)
        else:
            reporter = NullProgressReporter()

        self._pipeline.execute(output_stream=output_stream, progress=reporter)

    def export_to_bytes(self) -> bytes:
        """Convenience helper for programmatic usage."""
        buf = io.BytesIO()
        self.export(buf)
        return buf.getvalue()