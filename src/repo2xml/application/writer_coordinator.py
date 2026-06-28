# src/repo2xml/application/writer_coordinator.py
from __future__ import annotations

import io
import logging
from contextlib import contextmanager
from typing import BinaryIO, List, Optional

from repo2xml.application.contracts import (
    DocumentMetadataWriter,
    FileContentWriter,
    FileSectionWriter,
    StructureWriter,
)
from repo2xml.application.writer import BufferedTextWriter
from repo2xml.domain.model import ExportMeta, FileEntry, FilePayload, TokenStats
from repo2xml.services.output.targets import OutputTarget
from repo2xml.services.serialize.base import WriteFn

logger = logging.getLogger("repo2xml.writer_coordinator")


class WriterCoordinator:
    """
    Coordinates buffered writing through four separate writer components.

    Manages the output stream, buffer, and provides high-level methods
    for writing header, structure, files, statistics, and footer.
    Implements context manager protocol to ensure proper flushing and closing.
    """

    def __init__(
        self,
        metadata_writer: DocumentMetadataWriter,
        structure_writer: StructureWriter,
        section_writer: FileSectionWriter,
        content_writer: FileContentWriter,
        output_target: OutputTarget,
        *,
        buffer_chars: int = 64_000,
    ):
        self._metadata_writer = metadata_writer
        self._structure_writer = structure_writer
        self._section_writer = section_writer
        self._content_writer = content_writer
        self.output_target = output_target
        self.buffer_chars = buffer_chars

        self._stream: Optional[BinaryIO] = None
        self._text_wrapper: Optional[io.TextIOWrapper] = None
        self._buffered_writer: Optional[BufferedTextWriter] = None
        self._write_fn: Optional[WriteFn] = None

    # ------------------------------------------------------------------
    # Context manager protocol
    # ------------------------------------------------------------------

    def __enter__(self) -> WriterCoordinator:
        self._stream = self.output_target.open().__enter__()
        # Wrap binary stream as text with UTF-8 encoding
        self._text_wrapper = io.TextIOWrapper(self._stream, encoding="utf-8", newline="")
        self._buffered_writer = BufferedTextWriter(
            write_fn=self._text_wrapper.write,
            flush_fn=self._text_wrapper.flush,
            max_buffer_chars=self.buffer_chars,
        )
        self._write_fn = self._buffered_writer.write
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        try:
            self._buffered_writer.flush()
            self._text_wrapper.flush()
            self._text_wrapper.detach()
        except Exception as e:
            logger.error("Error during writer cleanup: %s", e)
        finally:
            self._stream = None
            self._text_wrapper = None
            self._buffered_writer = None
            self._write_fn = None

    # ------------------------------------------------------------------
    # High-level writing methods
    # ------------------------------------------------------------------

    def write_header(self, meta: ExportMeta) -> None:
        """Write the document header via the metadata writer."""
        if self._write_fn is None:
            raise RuntimeError("WriterCoordinator not opened; use 'with' context")
        self._metadata_writer.write_header(meta, self._write_fn)

    def write_structure(self, entries: List[FileEntry]) -> None:
        """Write the project structure via the structure writer."""
        if self._write_fn is None:
            raise RuntimeError("WriterCoordinator not opened; use 'with' context")
        self._structure_writer.write_structure(entries, self._write_fn)

    def write_files_open(self, mode: str) -> None:
        """Open the <files> section via the section writer."""
        if self._write_fn is None:
            raise RuntimeError("WriterCoordinator not opened; use 'with' context")
        self._section_writer.write_files_open(mode, self._write_fn)

    def write_file(self, entry: FileEntry, payload: FilePayload, token_count: Optional[int] = None) -> None:
        """Write a single file entry via the content writer."""
        if self._write_fn is None:
            raise RuntimeError("WriterCoordinator not opened; use 'with' context")
        self._content_writer.write_file(entry, payload, self._write_fn, token_count)

    def write_statistics(self, token_stats: Optional[TokenStats]) -> None:
        """Write aggregated statistics (if any) via the metadata writer."""
        if self._write_fn is None:
            raise RuntimeError("WriterCoordinator not opened; use 'with' context")
        self._metadata_writer.write_statistics(token_stats, self._write_fn)

    def write_footer(self) -> None:
        """Write the document footer via the metadata writer."""
        if self._write_fn is None:
            raise RuntimeError("WriterCoordinator not opened; use 'with' context")
        self._metadata_writer.write_footer(self._write_fn)

    def write_files_close(self) -> None:
        """Close the <files> section via the section writer."""
        if self._write_fn is None:
            raise RuntimeError("WriterCoordinator not opened; use 'with' context")
        self._section_writer.write_files_close(self._write_fn)

    # ------------------------------------------------------------------
    # Manual flush and close (for graceful interruption)
    # ------------------------------------------------------------------

    def flush(self) -> None:
        """Flush any pending buffered output."""
        if self._buffered_writer is not None:
            self._buffered_writer.flush()
        if self._text_wrapper is not None:
            self._text_wrapper.flush()

    def close(self) -> None:
        """
        Close the writer and underlying stream.

        This is primarily intended for use during interruption handling.
        """
        if self._stream is not None:
            try:
                self.flush()
                self._text_wrapper.detach()
                self._stream.close()
            except Exception as e:
                logger.error("Error during close: %s", e)
            finally:
                self._stream = None
                self._text_wrapper = None
                self._buffered_writer = None
                self._write_fn = None