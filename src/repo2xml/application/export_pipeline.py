# src/repo2xml/application/export_pipeline.py
from __future__ import annotations

import io
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import BinaryIO, List, Optional

from repo2xml.application.contracts import IngestorLike, ScannerLike
from repo2xml.application.filters import apply_file_filters
from repo2xml.application.policies import ExportPayloadBuilder
from repo2xml.application.progress import ProgressReporter
from repo2xml.application.writer import BufferedTextWriter
from repo2xml.config import ExportConfig, Mode
from repo2xml.domain.constants import SCHEMA_VERSION
from repo2xml.domain.model import (
    BinaryBase64Payload,
    BinaryHashPayload,
    ErrorPayload,
    ExportMeta,
    ExportStats,
    FileEntry,
    FilePayload,
    LinkPayload,
    MetadataPayload,
    SkippedPayload,
    TextPayload,
)
from repo2xml.services.serialize.base import WriteFn
from repo2xml.services.serialize.factory import get_format_factory
from repo2xml.utils.paths import format_root_path
from repo2xml.utils.version import tool_version

logger = logging.getLogger("repo2xml.pipeline")


class ExportPipeline:
    def __init__(
        self,
        *,
        root_path: Path,
        config: ExportConfig,
        scanner: ScannerLike,
        ingestor: IngestorLike,
    ):
        self.root_path = root_path.resolve()
        self.config = config
        self.scanner = scanner
        self.ingestor = ingestor
        self._payloads = ExportPayloadBuilder(config=self.config, ingestor=self.ingestor)

        factory = get_format_factory(config.format)
        self.serializer = factory.create_serializer(
            formatting=config.formatting.value,
            include_mtime=config.include_mtime,
            include_size=config.include_size,
            text_decode_errors=config.decode_errors.value,
        )

    def execute(self, *, output_stream: BinaryIO, progress: ProgressReporter) -> ExportStats:
        text_out = io.TextIOWrapper(output_stream, encoding="utf-8", newline="")
        try:
            writer = BufferedTextWriter(
                write_fn=text_out.write,
                flush_fn=text_out.flush,
                max_buffer_chars=self.config.write_buffer_chars,
            )

            progress.set_phase("Scanning")
            progress.set_total(None)
            logger.info("Scanning repository: %s", self.root_path)
            entries: List[FileEntry] = []
            for entry in self.scanner.scan():
                entries.append(entry)
                progress.advance(1)
            entries.sort(key=lambda e: e.rel_path)

            original_count = len(entries)
            entries = apply_file_filters(entries, self.config)
            if len(entries) != original_count:
                logger.info(
                    "File-level filters removed %d entries (%d remaining).",
                    original_count - len(entries),
                    len(entries),
                )

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
                progress.set_warning_count(total_warnings)

            total = len(entries)
            logger.info("Found %d files.", total)

            progress.set_phase("Processing")
            progress.set_total(total)

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
            self.serializer.write_structure(entries, writer.write)

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

            self.serializer.write_files_open(self.config.mode.value, writer.write)

            emitted = 0
            skipped = 0
            errors = 0
            skipped_by: dict[str, int] = {}
            errors_by: dict[str, int] = {}

            for entry in entries:
                payload = self._payloads.build(entry)
                self._dispatch_payload(entry, payload, writer.write)

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

                progress.set_postfix(entry.name)
                progress.advance(1)

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
            try:
                text_out.detach()
            except Exception:
                pass
            try:
                progress.finish()
            except Exception:
                pass

    def _dispatch_payload(self, entry: FileEntry, payload: FilePayload, write: WriteFn) -> None:
        """Manual dispatch to avoid dynamic lookup and ensure exhaustiveness."""
        if isinstance(payload, MetadataPayload):
            self.serializer.write_metadata(entry, payload, write)
        elif isinstance(payload, TextPayload):
            self.serializer.write_text(entry, payload, write)
        elif isinstance(payload, BinaryBase64Payload):
            self.serializer.write_binary_base64(entry, payload, write)
        elif isinstance(payload, BinaryHashPayload):
            self.serializer.write_binary_hash(entry, payload, write)
        elif isinstance(payload, LinkPayload):
            self.serializer.write_link(entry, payload, write)
        elif isinstance(payload, SkippedPayload):
            self.serializer.write_skipped(entry, payload, write)
        elif isinstance(payload, ErrorPayload):
            self.serializer.write_error(entry, payload, write)
        else:
            raise AssertionError(f"Unhandled payload type: {type(payload)}")