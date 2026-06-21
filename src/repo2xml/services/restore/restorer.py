# src/repo2xml/services/restore/restorer.py
from __future__ import annotations

import base64
import logging
import os
from pathlib import Path
from typing import Iterator, Optional

from repo2xml.domain.exceptions import RestoreError, UnsupportedPayloadError
from repo2xml.domain.model import (
    BinaryBase64Payload,
    BinaryHashPayload,
    ErrorPayload,
    FileEntry,
    LinkPayload,
    MetadataPayload,
    RestoreEntry,
    RestoreStats,
    SkippedPayload,
    TextPayload,
)

logger = logging.getLogger("repo2xml.restorer")


class FilesystemRestorer:
    """Creates directories and files on disk from a stream of RestoreEntry objects.

    Security: all paths are validated to stay inside `output_root`.
    """

    def __init__(
        self,
        output_root: Path,
        *,
        overwrite: bool = False,
        skip_existing: bool = True,
        restore_mtime: bool = True,
        create_empty_for_missing: bool = False,
    ):
        self.output_root = output_root.resolve()
        self.overwrite = overwrite
        self.skip_existing = skip_existing
        self.restore_mtime = restore_mtime
        self.create_empty_for_missing = create_empty_for_missing

    def restore(self, entries: Iterator[RestoreEntry]) -> RestoreStats:
        stats = RestoreStats(0, 0, 0, 0, 0, 0, {}, {})
        # First pass: collect directories to create
        dirs_to_create: set[str] = set()

        # We need to iterate entries twice? We'll buffer them.
        # Better: we can create directories on the fly when writing a file.
        buffered = list(entries)
        for re in buffered:
            dir_part = os.path.dirname(re.entry.rel_path)
            if dir_part:
                dirs_to_create.add(dir_part)

        # Create all directories first (safety: ensure inside root)
        for d in sorted(dirs_to_create):
            try:
                self._safe_mkdir(d)
                stats.dirs_created += 1
            except RestoreError as e:
                logger.warning("Skipping directory %s: %s", d, e)
                # continue with other dirs

        stats.files_total = len(buffered)
        for re in buffered:
            try:
                self._restore_entry(re, stats)
            except RestoreError as e:
                logger.error("Failed to restore %s: %s", re.entry.rel_path, e)
                stats.files_errors += 1
                stats.errors_by_code[e.__class__.__name__] = stats.errors_by_code.get(e.__class__.__name__, 0) + 1
            except Exception as e:
                logger.exception("Unexpected error restoring %s", re.entry.rel_path)
                stats.files_errors += 1
                stats.errors_by_code["internal"] = stats.errors_by_code.get("internal", 0) + 1
        return stats

    def _restore_entry(self, re: RestoreEntry, stats: RestoreStats) -> None:
        payload = re.payload
        if isinstance(payload, MetadataPayload):
            if self.create_empty_for_missing:
                self._write_empty_file(re.entry)
                stats.files_created += 1
            else:
                stats.files_skipped += 1
                stats.skipped_by_code["no_content"] = stats.skipped_by_code.get("no_content", 0) + 1
        elif isinstance(payload, TextPayload):
            self._write_text(re.entry, payload)
            stats.files_created += 1
        elif isinstance(payload, BinaryBase64Payload):
            self._write_binary_base64(re.entry, payload)
            stats.files_created += 1
        elif isinstance(payload, BinaryHashPayload):
            stats.files_skipped += 1
            stats.skipped_by_code["no_content"] = stats.skipped_by_code.get("no_content", 0) + 1
        elif isinstance(payload, LinkPayload):
            self._create_symlink(re.entry, payload)
            stats.symlinks_created += 1
        elif isinstance(payload, SkippedPayload) or isinstance(payload, ErrorPayload):
            stats.files_skipped += 1
            stats.skipped_by_code[payload.code.value] = stats.skipped_by_code.get(payload.code.value, 0) + 1
        else:
            raise UnsupportedPayloadError(f"Unsupported payload type: {type(payload)}")

    # ---- internal helpers ----

    def _abs_path(self, rel_path: str) -> Path:
        """Resolve relative path within output_root, raising on escape."""
        # Normalise to POSIX
        norm = rel_path.replace("\\", "/").lstrip("/")
        if ".." in norm.split("/"):
            raise RestoreError(f"Path escapes root: {rel_path!r}")
        result = (self.output_root / norm).resolve()
        if not str(result).startswith(str(self.output_root)):
            raise RestoreError(f"Path escapes root: {rel_path!r}")
        return result

    def _safe_mkdir(self, rel_dir: str) -> None:
        abs_dir = self._abs_path(rel_dir)
        if abs_dir.exists():
            return
        try:
            os.makedirs(abs_dir, exist_ok=True)
        except OSError as e:
            raise RestoreError(f"Cannot create directory {rel_dir}: {e}") from e

    def _write_empty_file(self, entry: FileEntry) -> None:
        fpath = self._abs_path(entry.rel_path)
        if fpath.exists() and self.skip_existing:
            return
        try:
            fpath.write_bytes(b"")
        except OSError as e:
            raise RestoreError(f"Cannot write {entry.rel_path}: {e}") from e
        self._apply_mtime(fpath, entry.mtime_ns)

    def _write_text(self, entry: FileEntry, payload: TextPayload) -> None:
        fpath = self._abs_path(entry.rel_path)
        if fpath.exists() and self.skip_existing:
            return
        try:
            # Write as UTF-8 by default; if original encoding known and needed, could re-encode.
            fpath.write_text(payload.text, encoding="utf-8")
        except OSError as e:
            raise RestoreError(f"Cannot write {entry.rel_path}: {e}") from e
        self._apply_mtime(fpath, entry.mtime_ns)

    def _write_binary_base64(self, entry: FileEntry, payload: BinaryBase64Payload) -> None:
        fpath = self._abs_path(entry.rel_path)
        if fpath.exists() and self.skip_existing:
            return
        try:
            data = b"".join(base64.b64decode(chunk) for chunk in payload.chunks)
            fpath.write_bytes(data)
        except OSError as e:
            raise RestoreError(f"Cannot write {entry.rel_path}: {e}") from e
        self._apply_mtime(fpath, entry.mtime_ns)

    def _create_symlink(self, entry: FileEntry, payload: LinkPayload) -> None:
        if not payload.link_target:
            raise RestoreError(f"Symlink without target: {entry.rel_path}")
        fpath = self._abs_path(entry.rel_path)
        if fpath.exists() or fpath.is_symlink():
            if self.skip_existing:
                return
        try:
            os.symlink(payload.link_target, fpath)
        except OSError as e:
            raise RestoreError(f"Cannot create symlink {entry.rel_path}: {e}") from e

    def _apply_mtime(self, path: Path, mtime_ns: int) -> None:
        if not self.restore_mtime or mtime_ns == 0:
            return
        try:
            os.utime(path, ns=(mtime_ns, mtime_ns))
        except OSError:
            pass