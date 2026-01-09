from __future__ import annotations

import io
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import BinaryIO, List, Optional

from repo2xml.application.contracts import IngestorLike, ScannerLike
from repo2xml.application.policies import PayloadBuilder
from repo2xml.application.progress import ProgressReporter
from repo2xml.application.writer import BufferedTextWriter
from repo2xml.config import Mode, Repo2XMLConfig
from repo2xml.domain.constants import SCHEMA_VERSION
from repo2xml.domain.model import (
    ErrorPayload,
    ExportMeta,
    ExportStats,
    FileEntry,
    SkippedPayload,
)
from repo2xml.services.serialize.base import Serializer
from repo2xml.utils.paths import format_root_path
from repo2xml.utils.version import tool_version

logger = logging.getLogger("repo2xml.pipeline")


class ExportPipeline:
    """
    Main orchestration pipeline.

    Phases:
      1) Scan: collect FileEntry list (needed for structure + deterministic order)
      2) Serialize:
         - header/meta
         - project_structure (if supported)
         - files (optional)
         - footer
    """

    def __init__(
        self,
        *,
        root_path: Path,
        config: Repo2XMLConfig,
        scanner: ScannerLike,
        ingestor: IngestorLike,
        serializer: Serializer,
    ):
        self.root_path = root_path.resolve()
        self.config = config
        self.scanner = scanner
        self.ingestor = ingestor
        self.serializer = serializer

        # Policies (payload builder)
        self._payloads = PayloadBuilder(config=self.config, ingestor=self.ingestor)

    def execute(self, *, output_stream: BinaryIO, progress: ProgressReporter) -> ExportStats:
        """
        Run the export and write to output_stream.

        output_stream is not closed by this function.
        """
        # Text writer wrapper for efficient UTF-8 streaming.
        text_out = io.TextIOWrapper(output_stream, encoding="utf-8", newline="")

        try:
            writer = BufferedTextWriter(
                write_fn=text_out.write,
                flush_fn=text_out.flush,
                max_buffer_chars=self.config.write_buffer_chars,
            )

            # Phase 1: scan (indeterminate progress, no total)
            progress.set_phase("Scanning")
            progress.set_total(None)

            logger.info("Scanning repository: %s", self.root_path)
            entries: List[FileEntry] = []
            for entry in self.scanner.scan():
                entries.append(entry)
                progress.advance(1)

            entries.sort(key=lambda e: e.rel_path)

            scan_warn: Optional[str] = None
            stats = getattr(self.scanner, "stats", None)
            if stats is not None and getattr(stats, "has_issues", None) is not None and stats.has_issues():
                scan_warn = stats.summary()
                logger.warning("Scan encountered filesystem errors (some entries skipped): %s", scan_warn)

            total = len(entries)
            logger.info("Found %d files.", total)

            # Phase 2: serialize/process files (determinate progress with total)
            progress.set_phase("Processing")
            progress.set_total(total)

            # Meta
            generated_at = None
            if self.config.include_timestamp:
                generated_at = datetime.now(timezone.utc).isoformat()

            meta = ExportMeta(
                root_path=format_root_path(self.root_path, self.config.root_path_mode),
                generated_at_utc=generated_at,
                tool_version=tool_version("repo2xml"),
                schema_version=SCHEMA_VERSION,
            )

            self.serializer.write_header(meta, writer.write)

            if self.serializer.supports_structure:
                self.serializer.write_structure(entries, writer.write)
            else:
                if self.config.mode == Mode.structure:
                    raise ValueError("Selected serializer does not support structure-only mode")

            if self.config.mode == Mode.structure:
                self.serializer.write_footer(writer.write)
                writer.flush()
                return ExportStats(
                    files_total=total,
                    files_emitted=0,
                    files_skipped=0,
                    files_errors=0,
                    skipped_by_code={},
                    errors_by_code={},
                    scan_warning_summary=scan_warn,
                )

            if self.serializer.supports_files_section:
                self.serializer.write_files_open(self.config.mode.value, writer.write)

            emitted = 0
            skipped = 0
            errors = 0
            skipped_by: dict[str, int] = {}
            errors_by: dict[str, int] = {}

            for entry in entries:
                payload = self._payloads.build(entry)
                self.serializer.write_file(entry, payload, writer.write)

                if isinstance(payload, ErrorPayload):
                    errors += 1
                    k = payload.code.value
                    errors_by[k] = errors_by.get(k, 0) + 1
                elif isinstance(payload, SkippedPayload):
                    skipped += 1
                    k = payload.code.value
                    skipped_by[k] = skipped_by.get(k, 0) + 1
                else:
                    emitted += 1

                progress.advance(1)

            if self.serializer.supports_files_section:
                self.serializer.write_files_close(writer.write)

            self.serializer.write_footer(writer.write)
            writer.flush()

            return ExportStats(
                files_total=total,
                files_emitted=emitted,
                files_skipped=skipped,
                files_errors=errors,
                skipped_by_code=skipped_by,
                errors_by_code=errors_by,
                scan_warning_summary=scan_warn,
            )

        finally:
            # Detach so we do not close the underlying binary stream.
            try:
                text_out.detach()
            except Exception:
                pass
            try:
                progress.finish()
            except Exception:
                pass