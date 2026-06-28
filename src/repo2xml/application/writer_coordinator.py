# src/repo2xml/application/writer_coordinator.py
from __future__ import annotations

import io
import logging
from typing import BinaryIO, List, Optional

from repo2xml.contracts import DocumentWriter
from repo2xml.application.writer import BufferedTextWriter
from repo2xml.domain.model import ExportMeta, FileEntry, FilePayload, TokenStats
from repo2xml.services.output.targets import OutputTarget
from repo2xml.services.serialize.base import WriteFn

logger = logging.getLogger("repo2xml.writer_coordinator")


class WriterCoordinator:
    """
    Coordinates buffered writing through a single DocumentWriter.

    Manages the output stream, buffer, and provides high-level methods
    for writing header, structure, files, statistics, and footer.
    Implements context manager protocol to ensure proper flushing and closing.
    """

    def __init__(
        self,
        document_writer: DocumentWriter,
        output_target: OutputTarget,
        *,
        buffer_chars: int = 64_000,
    ):
        self._document_writer = document_writer
        self.output_target = output_target
        self.buffer_chars = buffer_chars

        self._cm = None
        self._stream: Optional[BinaryIO] = None
        self._text_wrapper: Optional[io.TextIOWrapper] = None
        self._buffered_writer: Optional[BufferedTextWriter] = None
        self._write_fn: Optional[WriteFn] = None

    def __enter__(self) -> WriterCoordinator:
        self._cm = self.output_target.open()
        self._stream = self._cm.__enter__()
        self._text_wrapper = io.TextIOWrapper(self._stream, encoding="utf-8", newline="")
        self._buffered_writer = BufferedTextWriter(
            write_fn=self._text_wrapper.write,
            flush_fn=self._text_wrapper.flush,
            max_buffer_chars=self.buffer_chars,
        )
        self._write_fn = self._buffered_writer.write
        self._document_writer.set_write_fn(self._write_fn)
        
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        has_exception = exc_type is not None

        # If an exception occurred, we rely on the document writer to close properly,
        # but we also flush buffers.
        try:
            if self._buffered_writer is not None:
                self._buffered_writer.flush()
            if self._text_wrapper is not None:
                self._text_wrapper.flush()
        except Exception as e:
            if has_exception:
                logger.error("Error during final flush (suppressed): %s", e)
            else:
                logger.error("Error during final flush: %s", e)
                raise RuntimeError("Failed to flush output") from e

        if self._text_wrapper is not None:
            try:
                self._text_wrapper.detach()
            except Exception as e:
                if has_exception:
                    logger.error("Error detaching TextIOWrapper (suppressed): %s", e)
                else:
                    logger.error("Error detaching TextIOWrapper: %s", e)
                    raise RuntimeError("Failed to detach TextIOWrapper") from e

        if self._cm is not None:
            try:
                self._cm.__exit__(exc_type, exc_val, exc_tb)
            except Exception as e:
                if has_exception:
                    logger.error("Error while exiting output target context (suppressed): %s", e)
                else:
                    logger.error("Error while exiting output target context: %s", e)
                    raise RuntimeError("Failed to close output target") from e

        self._stream = None
        self._text_wrapper = None
        self._buffered_writer = None
        self._write_fn = None
        self._cm = None

    def write_header(self, meta: ExportMeta) -> None:
        if self._write_fn is None:
            raise RuntimeError("WriterCoordinator not opened; use 'with' context")
        self._document_writer.begin_document(meta)

    def write_structure(self, entries: List[FileEntry]) -> None:
        if self._write_fn is None:
            raise RuntimeError("WriterCoordinator not opened; use 'with' context")
        self._document_writer.write_structure(entries)

    def write_files_open(self, mode: str) -> None:
        if self._write_fn is None:
            raise RuntimeError("WriterCoordinator not opened; use 'with' context")
        self._document_writer.begin_files_section(mode)

    def write_file(self, entry: FileEntry, payload: FilePayload, token_count: Optional[int] = None) -> None:
        if self._write_fn is None:
            raise RuntimeError("WriterCoordinator not opened; use 'with' context")
        self._document_writer.write_file(entry, payload, token_count)

    def write_statistics(self, token_stats: Optional[TokenStats]) -> None:
        if self._write_fn is None:
            raise RuntimeError("WriterCoordinator not opened; use 'with' context")
        self._document_writer.write_statistics(token_stats)

    def write_footer(self) -> None:
        if self._write_fn is None:
            raise RuntimeError("WriterCoordinator not opened; use 'with' context")
        self._document_writer.end_document()

    def write_files_close(self) -> None:
        if self._write_fn is None:
            raise RuntimeError("WriterCoordinator not opened; use 'with' context")
        self._document_writer.end_files_section()

    def flush(self) -> None:
        if self._buffered_writer is not None:
            self._buffered_writer.flush()
        if self._text_wrapper is not None:
            self._text_wrapper.flush()