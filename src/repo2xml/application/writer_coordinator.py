# src/repo2xml/application/writer_coordinator.py
from __future__ import annotations

import io
import logging
from typing import BinaryIO, List, Optional

from repo2xml.contracts import (
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

        self._cm = None  # Context manager from output_target.open()
        self._stream: Optional[BinaryIO] = None
        self._text_wrapper: Optional[io.TextIOWrapper] = None
        self._buffered_writer: Optional[BufferedTextWriter] = None
        self._write_fn: Optional[WriteFn] = None

        # Flag to track whether the <files> section has been opened.
        # Used to gracefully close the document on interruption.
        self._files_section_open: bool = False

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
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        # If an exception occurred and the files section is still open,
        # close it and write the footer to produce a valid XML document.
        if exc_type is not None and self._files_section_open:
            try:
                self.write_files_close()
                self.write_footer()
                self._files_section_open = False
            except Exception as e:
                logger.error("Error while closing document after interruption: %s", e)

        # Flush any pending data before detaching and closing the stream.
        try:
            if self._buffered_writer is not None:
                self._buffered_writer.flush()
            if self._text_wrapper is not None:
                self._text_wrapper.flush()
        except Exception as e:
            logger.error("Error during final flush: %s", e)

        # Detach the TextIOWrapper from the underlying stream without closing it.
        # This allows the underlying stream (e.g., BytesIO for clipboard) to remain
        # open so that the output target can read the data after the writer finishes.
        if self._text_wrapper is not None:
            try:
                self._text_wrapper.detach()
            except Exception as e:
                logger.error("Error detaching TextIOWrapper: %s", e)

        # Exit the output target context (this will close the stream and,
        # for ClipboardTarget, copy the data to the clipboard).
        if self._cm is not None:
            try:
                self._cm.__exit__(exc_type, exc_val, exc_tb)
            except Exception as e:
                logger.error("Error while exiting output target context: %s", e)

        self._stream = None
        self._text_wrapper = None
        self._buffered_writer = None
        self._write_fn = None
        self._cm = None

    def write_header(self, meta: ExportMeta) -> None:
        if self._write_fn is None:
            raise RuntimeError("WriterCoordinator not opened; use 'with' context")
        self._metadata_writer.write_header(meta, self._write_fn)

    def write_structure(self, entries: List[FileEntry]) -> None:
        if self._write_fn is None:
            raise RuntimeError("WriterCoordinator not opened; use 'with' context")
        self._structure_writer.write_structure(entries, self._write_fn)

    def write_files_open(self, mode: str) -> None:
        if self._write_fn is None:
            raise RuntimeError("WriterCoordinator not opened; use 'with' context")
        self._section_writer.write_files_open(mode, self._write_fn)
        self._files_section_open = True

    def write_file(self, entry: FileEntry, payload: FilePayload, token_count: Optional[int] = None) -> None:
        if self._write_fn is None:
            raise RuntimeError("WriterCoordinator not opened; use 'with' context")
        self._content_writer.write_file(entry, payload, self._write_fn, token_count)

    def write_statistics(self, token_stats: Optional[TokenStats]) -> None:
        if self._write_fn is None:
            raise RuntimeError("WriterCoordinator not opened; use 'with' context")
        self._metadata_writer.write_statistics(token_stats, self._write_fn)

    def write_footer(self) -> None:
        if self._write_fn is None:
            raise RuntimeError("WriterCoordinator not opened; use 'with' context")
        self._metadata_writer.write_footer(self._write_fn)

    def write_files_close(self) -> None:
        if self._write_fn is None:
            raise RuntimeError("WriterCoordinator not opened; use 'with' context")
        self._section_writer.write_files_close(self._write_fn)
        self._files_section_open = False

    def flush(self) -> None:
        if self._buffered_writer is not None:
            self._buffered_writer.flush()
        if self._text_wrapper is not None:
            self._text_wrapper.flush()

    def close(self) -> None:
        # This method is kept for backward compatibility but should not be used
        # with the context manager protocol. Use the 'with' statement instead.
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