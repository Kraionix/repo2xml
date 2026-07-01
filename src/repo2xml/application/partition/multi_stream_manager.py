# src/repo2xml/application/partition/multi_stream_manager.py
from __future__ import annotations

import contextlib
import io
from pathlib import Path
from typing import Callable, List, Optional, Tuple

from repo2xml.application.writer_coordinator import WriterCoordinator
from repo2xml.config import PartitionConfig, Mode
from repo2xml.contracts import DocumentWriter, ProgressReporter, TokenCounter
from repo2xml.domain.model import ExportMeta, FileEntry, FilePayload, TokenStats
from repo2xml.services.output.targets import (
    ClipboardWithPauseTarget,
    FileTarget,
    OutputTarget,
)

from .buffer_manager import BufferManager, BufferItem
from .decision_strategy import IPartitionDecisionStrategy, TokenBasedStrategy


class MultiStreamManager:
    """
    Coordinates the generation of multiple parts (XML fragments) during export.
    """

    def __init__(
        self,
        config: PartitionConfig,
        mode: Mode,
        token_counter: TokenCounter,
        document_writer_factory: Callable[..., DocumentWriter],
        progress_reporter: Optional[ProgressReporter] = None,
        buffer_chars: int = 64000,
    ) -> None:
        self._config = config
        self._mode = mode
        self._token_counter = token_counter
        self._document_writer_factory = document_writer_factory
        self._progress = progress_reporter
        self._buffer_chars = buffer_chars

        # State
        self._meta: Optional[ExportMeta] = None
        self._structure_entries: List[FileEntry] = []
        self._structure_xml: Optional[str] = None
        self._current_writer: Optional[WriterCoordinator] = None
        self._current_part_number: int = 0
        self._parts_created: int = 0
        self._buffer_manager: Optional[BufferManager] = None
        self._strategy: Optional[IPartitionDecisionStrategy] = None
        self._exit_stack = contextlib.ExitStack()
        self._is_file_part_open: bool = False
        self._is_closed: bool = False

        # Statistics per part
        self._part_stats: List[Tuple[int, int]] = []  # (file_count, tokens)

    def __enter__(self) -> MultiStreamManager:
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()

    def _ensure_initialized(self) -> None:
        """Lazy initialization: create BufferManager and strategy after structure is serialized."""
        if self._buffer_manager is not None:
            return

        # Create a temporary writer to serialize structure
        struct_writer = self._document_writer_factory(
            root_tag="repository_context",
            include_structure=True,
            formatting="compact",
            include_mtime=True,
            include_size=True,
            text_decode_errors="replace",
            write_fn=lambda s: None,
        )
        # Serialize structure to string
        output = io.StringIO()
        struct_writer.set_write_fn(output.write)
        struct_writer.begin_document(self._meta)
        struct_writer.write_structure(self._structure_entries)
        struct_writer.end_document()
        self._structure_xml = output.getvalue()
        output.close()

        # Create BufferManager and strategy
        doc_writer_for_buffer = self._document_writer_factory(
            root_tag="repository_part",
            include_structure=False,
            formatting="compact",
            include_mtime=True,
            include_size=True,
            text_decode_errors="replace",
            write_fn=lambda s: None,
        )
        self._buffer_manager = BufferManager(
            max_tokens=self._config.max_tokens_per_part,
            token_counter=self._token_counter,
            document_writer=doc_writer_for_buffer,
        )
        self._strategy = TokenBasedStrategy()

        # Write the structure part (part 0)
        self._write_structure_part()

        # If mode is structure, we are done; otherwise open the first file part
        if self._mode != Mode.structure:
            self._open_file_part()

    def _write_structure_part(self) -> None:
        """Write the structure-only part (part 0) and close it."""
        if self._structure_xml is None:
            raise RuntimeError("Structure not serialized yet")

        target = self._create_output_target(part_number=0)
        writer = self._create_writer(target, root_tag="repository_context", include_structure=True)
        # Write the full structure XML
        writer._document_writer._write(self._structure_xml)
        # Close the writer (this also closes the stream)
        writer.__exit__(None, None, None)
        self._parts_created += 1
        self._current_part_number = 1

    def _open_file_part(self) -> None:
        """Open a new part for file entries (part number >= 1)."""
        target = self._create_output_target(part_number=self._current_part_number)
        writer = self._create_writer(target, root_tag="repository_part", include_structure=False)
        writer.write_header(self._meta)
        writer.write_files_open("full")
        self._current_writer = writer
        self._is_file_part_open = True
        self._parts_created += 1

    def _create_output_target(self, part_number: int) -> OutputTarget:
        """Factory for OutputTarget based on configuration."""
        if self._config.clipboard_mode:
            return ClipboardWithPauseTarget()
        else:
            pattern = self._config.output_pattern or "context_part_{n:03d}.xml"
            path = Path(pattern.format(n=part_number))
            return FileTarget(path)

    def _create_writer(self, target: OutputTarget, root_tag: str, include_structure: bool) -> WriterCoordinator:
        """Create a WriterCoordinator for a specific part."""
        doc_writer = self._document_writer_factory(
            root_tag=root_tag,
            include_structure=include_structure,
            formatting="compact",
            include_mtime=True,
            include_size=True,
            text_decode_errors="replace",
            write_fn=lambda s: None,
        )
        writer = WriterCoordinator(
            document_writer=doc_writer,
            output_target=target,
            buffer_chars=self._buffer_chars,
        )
        writer.__enter__()
        self._exit_stack.callback(writer.__exit__, None, None, None)
        return writer

    def _switch_to_new_file_part(self) -> None:
        """
        Close current file part and open a new one with a fresh buffer.
        This ensures that the buffer is flushed to the current part and a new
        empty buffer is created for the next part.
        """
        # 1. Flush the current buffer to the current part
        if self._current_writer is not None and self._buffer_manager is not None:
            if not self._buffer_manager.is_empty():
                items = self._buffer_manager.flush_buffer()
                for item in items:
                    self._current_writer.write_file(item.entry, item.payload, item.original_token_count)

            # 2. Close the current part
            if self._is_file_part_open:
                self._current_writer.write_files_close()
                self._is_file_part_open = False
            self._current_writer.write_statistics(None)
            self._current_writer.write_footer()
            self._current_writer.__exit__(None, None, None)
            self._current_writer = None

        # 3. Increment part number
        self._current_part_number += 1

        # 4. Create a NEW BufferManager for the new part
        doc_writer_for_buffer = self._document_writer_factory(
            root_tag="repository_part",
            include_structure=False,
            formatting="compact",
            include_mtime=True,
            include_size=True,
            text_decode_errors="replace",
            write_fn=lambda s: None,
        )
        self._buffer_manager = BufferManager(
            max_tokens=self._config.max_tokens_per_part,
            token_counter=self._token_counter,
            document_writer=doc_writer_for_buffer,
        )
        # The strategy is stateless, we can reuse the same instance
        self._strategy = TokenBasedStrategy()

        # 5. Open the new part
        self._open_file_part()

    def _close_current_file_part(self) -> None:
        """
        Close the current file part (end files section, but keep document open for stats).
        Also flush any remaining buffer.
        """
        if self._current_writer is not None and self._is_file_part_open:
            # Flush remaining buffer before closing
            if not self._buffer_manager.is_empty():
                items = self._buffer_manager.flush_buffer()
                for item in items:
                    self._current_writer.write_file(item.entry, item.payload, item.original_token_count)

            self._current_writer.write_files_close()
            self._is_file_part_open = False

    # ------------------------------------------------------------------
    # Public methods matching WriterCoordinator interface
    # ------------------------------------------------------------------

    def write_header(self, meta: ExportMeta) -> None:
        """Store meta; actual writing happens during structure part."""
        self._meta = meta

    def write_structure(self, entries: List[FileEntry]) -> None:
        """Serialize and store structure; create first part."""
        self._structure_entries = entries
        self._ensure_initialized()

    def write_files_open(self, mode: str) -> None:
        """
        Open the files section. For partitioned output, this is a no-op
        because the file part is already opened in write_structure.
        """
        if self._mode != Mode.structure and not self._is_file_part_open:
            self._open_file_part()

    def write_file(self, entry: FileEntry, payload: FilePayload, token_count: Optional[int] = None) -> None:
        """Add a file to the buffer, switch part if limit exceeded."""
        self._ensure_initialized()
        if token_count is None:
            token_count = 0

        # Add file to buffer
        self._buffer_manager.add_file(entry, payload, token_count)

        # Check strategy
        if self._strategy.should_start_new_part(self._buffer_manager, 0):
            # Rollback the last addition
            rolled_back = self._buffer_manager.rollback_last()
            if rolled_back is None:
                return
            # Switch to new part (this will flush the buffer and create a new one)
            self._switch_to_new_file_part()
            # Now add the rolled-back file to the new part's buffer
            self._buffer_manager.add_file(rolled_back.entry, rolled_back.payload, rolled_back.original_token_count)

        # Update progress if available
        if self._progress:
            self._progress.advance(1)
            self._progress.set_postfix(entry.name)

    def write_files_close(self) -> None:
        """
        Close the files section. For partitioned output, this closes the
        current file part (but keeps it open for final statistics and footer).
        """
        if self._mode == Mode.structure:
            return
        # Flush remaining buffer to current writer
        if not self._buffer_manager.is_empty():
            items = self._buffer_manager.flush_buffer()
            for item in items:
                self._current_writer.write_file(item.entry, item.payload, item.original_token_count)
        # Close the files section
        self._close_current_file_part()

    def write_statistics(self, stats: Optional[TokenStats]) -> None:
        """Write statistics to the current open part (if any)."""
        if self._mode == Mode.structure:
            return
        if self._current_writer is not None and self._is_file_part_open:
            self._current_writer.write_statistics(stats)

    def write_footer(self) -> None:
        """
        Write the document footer. For partitioned output, this closes the
        last file part completely.
        """
        if self._mode == Mode.structure:
            return
        if self._current_writer is not None and self._is_file_part_open:
            self._current_writer.write_statistics(None)
            self._current_writer.write_footer()
            self._current_writer.__exit__(None, None, None)
            self._current_writer = None
            self._is_file_part_open = False

    def flush(self) -> None:
        """Flush the current writer buffer if any."""
        if self._current_writer is not None:
            self._current_writer.flush()

    def close(self) -> None:
        """Close all resources."""
        if self._is_closed:
            return
        self._is_closed = True
        # Ensure any remaining buffer is flushed
        if self._buffer_manager is not None and not self._buffer_manager.is_empty():
            items = self._buffer_manager.flush_buffer()
            if self._current_writer is not None:
                for item in items:
                    self._current_writer.write_file(item.entry, item.payload, item.original_token_count)
        # Close current writer if still open
        if self._current_writer is not None:
            if self._is_file_part_open:
                self._current_writer.write_files_close()
                self._current_writer.write_statistics(None)
                self._current_writer.write_footer()
            self._current_writer.__exit__(None, None, None)
            self._current_writer = None
            self._is_file_part_open = False
        # Close all resources via exit stack
        self._exit_stack.close()

    # ------------------------------------------------------------------
    # Compatibility: aliases for old names (just in case)
    # ------------------------------------------------------------------

    def begin_files_section(self, mode: str) -> None:
        """Alias for write_files_open (legacy)."""
        self.write_files_open(mode)

    def end_files_section(self) -> None:
        """Alias for write_files_close (legacy)."""
        self.write_files_close()

    def end_document(self) -> None:
        """Alias for write_footer (legacy)."""
        self.write_footer()