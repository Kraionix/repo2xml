from __future__ import annotations

import io
import logging
import os
from datetime import datetime, timezone
from importlib import metadata as importlib_metadata
from pathlib import Path
from typing import BinaryIO, List, Optional

from repo2xml.application.progress import ProgressReporter
from repo2xml.config import BinaryMode, Mode, Repo2XMLConfig, RootPathMode, SymlinkFilesMode
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
from repo2xml.services.ingest.ingestor import IngestResult, StandardIngestor
from repo2xml.services.scan.scanner import FileSystemScanner
from repo2xml.services.serialize.base import Serializer

logger = logging.getLogger("repo2xml.pipeline")


def _tool_version() -> str:
    """Best-effort read package version from metadata."""
    try:
        return importlib_metadata.version("repo2xml")
    except Exception:
        return "0.0.0"


def _posix_relpath(path: Path, base: Path) -> Optional[str]:
    """Return POSIX relative path if possible."""
    try:
        rel = os.path.relpath(path.resolve(), base.resolve())
        rel = rel.replace("\\", "/")
        return rel if rel else "."
    except Exception:
        return None


def _format_root_path(root: Path, mode: RootPathMode) -> str:
    """
    Format meta.root_path according to config.

    Always uses POSIX separators for reproducibility.
    """
    if mode == RootPathMode.absolute:
        return root.as_posix()

    if mode == RootPathMode.relative:
        cwd = Path.cwd().resolve()
        rel = _posix_relpath(root, cwd)
        if rel is not None:
            return rel
        return (root.name or ".").replace("\\", "/")

    if mode == RootPathMode.redact:
        return "<redacted>"

    # Defensive fallback
    return root.as_posix()


class ExportPipeline:
    """
    Main orchestration pipeline.

    Phases:
      1) Scan: collect FileEntry list (needed for structure + deterministic order)
      2) Serialize:
         - header/meta
         - project_structure
         - files (optional)
         - footer
    """

    def __init__(
        self,
        *,
        root_path: Path,
        config: Repo2XMLConfig,
        scanner: FileSystemScanner,
        ingestor: StandardIngestor,
        serializer: Serializer,
    ):
        self.root_path = root_path.resolve()
        self.config = config
        self.scanner = scanner
        self.ingestor = ingestor
        self.serializer = serializer

    def execute(self, *, output_stream: BinaryIO, progress: ProgressReporter) -> ExportStats:
        """
        Run the export and write to output_stream.

        output_stream is not closed by this function.
        """
        # Text writer wrapper for efficient UTF-8 streaming.
        text_out = io.TextIOWrapper(output_stream, encoding="utf-8", newline="")

        def write(s: str) -> None:
            text_out.write(s)

        try:
            # Phase 1: scan
            logger.info("Scanning repository: %s", self.root_path)
            entries: List[FileEntry] = list(self.scanner.scan())
            entries.sort(key=lambda e: e.rel_path)

            scan_warn: Optional[str] = None
            if getattr(self.scanner, "stats", None) is not None and self.scanner.stats.has_issues():
                scan_warn = self.scanner.stats.summary()
                logger.warning("Scan encountered filesystem errors (some entries skipped): %s", scan_warn)

            total = len(entries)
            progress.set_total(total)
            logger.info("Found %d files.", total)

            # Meta
            generated_at = None
            if self.config.include_timestamp:
                generated_at = datetime.now(timezone.utc).isoformat()

            meta = ExportMeta(
                root_path=_format_root_path(self.root_path, self.config.root_path_mode),
                generated_at_utc=generated_at,
                tool_version=_tool_version(),
                schema_version="1.0",
            )

            # Phase 2: serialize
            self.serializer.write_header(meta, write)
            self.serializer.write_structure(entries, write)

            if self.config.mode == Mode.structure:
                self.serializer.write_footer(write)
                text_out.flush()
                return ExportStats(
                    files_total=total,
                    files_emitted=0,
                    files_skipped=0,
                    files_errors=0,
                    scan_warning_summary=scan_warn,
                )

            self.serializer.write_files_open(self.config.mode.value, write)

            emitted = 0
            skipped = 0
            errors = 0

            for entry in entries:
                payload = self._build_payload(entry)
                self.serializer.write_file(entry, payload, write)

                if isinstance(payload, ErrorPayload):
                    errors += 1
                elif isinstance(payload, SkippedPayload):
                    skipped += 1
                else:
                    emitted += 1

                progress.advance(1)

            self.serializer.write_files_close(write)
            self.serializer.write_footer(write)
            text_out.flush()

            return ExportStats(
                files_total=total,
                files_emitted=emitted,
                files_skipped=skipped,
                files_errors=errors,
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

    def _build_payload(self, entry: FileEntry) -> FilePayload:
        """
        Decide how to emit this entry.

        This is the central policy decision point:
        - mode (structure/metadata/full)
        - symlink handling
        - binary handling
        - text processors
        """
        # Symlink-as-link overrides any content reads.
        if entry.is_symlink and self.config.symlinks_files == SymlinkFilesMode.as_link:
            return LinkPayload(link_target=entry.symlink_target)

        # Metadata mode: never read content.
        if self.config.mode == Mode.metadata:
            return MetadataPayload()

        # Full mode: ingest content.
        res = self.ingestor.ingest(entry.abs_path)

        if res.kind == "text":
            text = res.text or ""
            for proc in self.config.text_processors:
                try:
                    text = proc(text)
                except Exception as e:
                    # Processor failures should not crash export; emit an error marker.
                    return ErrorPayload(message=f"Text processor error: {e}")
            return TextPayload(text=text, encoding=res.encoding)

        if res.kind == "binary":
            if self.config.binary == BinaryMode.skip:
                return SkippedPayload(reason="Skipped: Binary file detected")

            if self.config.binary == BinaryMode.hash:
                try:
                    h = self.ingestor.sha256_file(entry.abs_path)
                except OSError as e:
                    return ErrorPayload(message=f"Error hashing file: {e}")
                return BinaryHashPayload(sha256_hex=h)

            if self.config.binary == BinaryMode.base64:
                try:
                    chunks = self.ingestor.iter_base64_chunks(entry.abs_path)
                except OSError as e:
                    return ErrorPayload(message=f"Error base64-encoding file: {e}")
                return BinaryBase64Payload(chunks=chunks)

            return SkippedPayload(reason="Skipped: Unknown binary mode")

        if res.kind == "skip":
            return SkippedPayload(reason=res.reason or "Skipped")

        if res.kind == "error":
            return ErrorPayload(message=res.reason or "Error")

        return ErrorPayload(message="Unknown ingest result")