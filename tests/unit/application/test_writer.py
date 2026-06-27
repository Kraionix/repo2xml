# tests/unit/application/test_writer.py
"""Unit tests for BufferedTextWriter and WriterCoordinator."""

from io import StringIO
from unittest.mock import MagicMock, call

import pytest

from repo2xml.application.writer import BufferedTextWriter
from repo2xml.application.writer_coordinator import WriterCoordinator
from repo2xml.domain.model import ExportMeta, FileEntry, TextPayload, TokenStats
from repo2xml.services.output.targets import OutputTarget


class TestBufferedTextWriter:
    def test_write_passthrough_when_buffer_zero(self) -> None:
        write_fn = MagicMock()
        flush_fn = MagicMock()
        writer = BufferedTextWriter(write_fn, flush_fn, max_buffer_chars=0)

        writer.write("hello")
        writer.write("world")
        writer.flush()

        write_fn.assert_has_calls([call("hello"), call("world")])
        # flush_fn is not called because buffer is empty (passthrough mode)
        flush_fn.assert_not_called()

    def test_buffering_and_auto_flush(self) -> None:
        write_fn = MagicMock()
        flush_fn = MagicMock()
        writer = BufferedTextWriter(write_fn, flush_fn, max_buffer_chars=10)

        writer.write("abc")  # 3 chars
        write_fn.assert_not_called()
        writer.write("defghijklm")  # 10 chars, total 13 -> flush
        write_fn.assert_called_once_with("abcdefghijklm")
        flush_fn.assert_called_once()

        # After flush, buffer cleared
        write_fn.reset_mock()
        flush_fn.reset_mock()
        writer.write("n")  # 1 char
        write_fn.assert_not_called()

        writer.flush()
        write_fn.assert_called_once_with("n")
        flush_fn.assert_called_once()

    def test_flush_with_empty_buffer(self) -> None:
        write_fn = MagicMock()
        flush_fn = MagicMock()
        writer = BufferedTextWriter(write_fn, flush_fn, max_buffer_chars=10)
        writer.flush()
        write_fn.assert_not_called()
        flush_fn.assert_not_called()


class TestWriterCoordinator:
    @pytest.fixture
    def mock_serializer(self) -> MagicMock:
        return MagicMock()

    @pytest.fixture
    def mock_output_target(self) -> MagicMock:
        target = MagicMock(spec=OutputTarget)
        # Simulate context manager
        mock_cm = MagicMock()
        target.open.return_value = mock_cm
        mock_cm.__enter__ = MagicMock(return_value=MagicMock())
        mock_cm.__exit__ = MagicMock(return_value=False)
        return target

    @pytest.fixture
    def coordinator(self, mock_serializer, mock_output_target) -> WriterCoordinator:
        return WriterCoordinator(
            serializer=mock_serializer,
            output_target=mock_output_target,
            buffer_chars=10,
        )

    def test_context_manager(self, coordinator, mock_output_target) -> None:
        with coordinator as c:
            assert c is coordinator
            # __enter__ called on target
            mock_output_target.open.assert_called_once()
            # __enter__ called on the returned context manager
            mock_output_target.open.return_value.__enter__.assert_called_once()

        # __exit__ on the context manager is NOT called by WriterCoordinator
        # because it closes the stream directly. So we don't assert it.
        # Instead, we check that the coordinator's internal state is cleaned up.
        assert coordinator._stream is None
        assert coordinator._text_wrapper is None
        assert coordinator._buffered_writer is None

    def test_write_header(self, coordinator, mock_serializer) -> None:
        meta = ExportMeta(root_path="/", generated_at_utc=None, tool_version="0", schema_version="1")
        with coordinator:
            coordinator.write_header(meta)
            mock_serializer.write_header.assert_called_once_with(meta, coordinator._write_fn)

    def test_write_structure(self, coordinator, mock_serializer) -> None:
        entries = [MagicMock(spec=FileEntry)]
        with coordinator:
            coordinator.write_structure(entries)
            mock_serializer.write_structure.assert_called_once_with(entries, coordinator._write_fn)

    def test_write_files_open(self, coordinator, mock_serializer) -> None:
        with coordinator:
            coordinator.write_files_open("full")
            mock_serializer.write_files_open.assert_called_once_with("full", coordinator._write_fn)

    def test_write_file(self, coordinator, mock_serializer) -> None:
        entry = MagicMock(spec=FileEntry)
        payload = TextPayload(text="test")
        with coordinator:
            coordinator.write_file(entry, payload, token_count=42)
            mock_serializer.write_file.assert_called_once_with(entry, payload, coordinator._write_fn, 42)

    def test_write_statistics(self, coordinator, mock_serializer) -> None:
        stats = TokenStats(total_tokens=100)
        with coordinator:
            coordinator.write_statistics(stats)
            mock_serializer.write_statistics.assert_called_once_with(stats, coordinator._write_fn)

    def test_write_footer(self, coordinator, mock_serializer) -> None:
        with coordinator:
            coordinator.write_footer()
            mock_serializer.write_footer.assert_called_once_with(coordinator._write_fn)

    def test_write_files_close(self, coordinator, mock_serializer) -> None:
        with coordinator:
            coordinator.write_files_close()
            mock_serializer.write_files_close.assert_called_once_with(coordinator._write_fn)

    def test_write_without_context_raises(self, coordinator) -> None:
        with pytest.raises(RuntimeError, match="not opened"):
            coordinator.write_header(MagicMock())

    def test_close_handles_errors(self, coordinator, mock_serializer, mock_output_target) -> None:
        # Mock the text wrapper to raise on flush
        coordinator._text_wrapper = MagicMock()
        coordinator._text_wrapper.flush.side_effect = OSError("flush failed")
        coordinator._stream = MagicMock()

        # close() should catch and log, not raise
        coordinator.close()
        # After close, stream is None
        assert coordinator._stream is None
        assert coordinator._text_wrapper is None
        assert coordinator._buffered_writer is None