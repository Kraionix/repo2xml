"""Unit tests for BufferedTextWriter and WriterCoordinator."""

import io
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


# Helper class to provide a real BytesIO stream for testing
class BytesIOOutputTarget(OutputTarget):
    def __init__(self) -> None:
        self._buffer = io.BytesIO()

    def open(self):
        class CM:
            def __enter__(self2):
                return self._buffer
            def __exit__(self2, *args):
                pass
        return CM()

    def describe(self) -> str:
        return "test-bytesio"

    def getvalue(self) -> bytes:
        return self._buffer.getvalue()


class TestWriterCoordinator:
    @pytest.fixture
    def mock_metadata_writer(self) -> MagicMock:
        return MagicMock()

    @pytest.fixture
    def mock_structure_writer(self) -> MagicMock:
        return MagicMock()

    @pytest.fixture
    def mock_section_writer(self) -> MagicMock:
        return MagicMock()

    @pytest.fixture
    def mock_content_writer(self) -> MagicMock:
        return MagicMock()

    @pytest.fixture
    def real_output_target(self) -> BytesIOOutputTarget:
        return BytesIOOutputTarget()

    @pytest.fixture
    def coordinator(
        self,
        mock_metadata_writer,
        mock_structure_writer,
        mock_section_writer,
        mock_content_writer,
        real_output_target,
    ) -> WriterCoordinator:
        return WriterCoordinator(
            metadata_writer=mock_metadata_writer,
            structure_writer=mock_structure_writer,
            section_writer=mock_section_writer,
            content_writer=mock_content_writer,
            output_target=real_output_target,
            buffer_chars=10,
        )

    def test_context_manager(self, coordinator, real_output_target) -> None:
        with coordinator as c:
            assert c is coordinator
            assert coordinator._stream is not None
            assert coordinator._text_wrapper is not None
            assert coordinator._buffered_writer is not None
        # After exit, resources should be cleaned up
        assert coordinator._stream is None
        assert coordinator._text_wrapper is None
        assert coordinator._buffered_writer is None

    def test_write_header(self, coordinator, mock_metadata_writer) -> None:
        meta = ExportMeta(root_path="/", generated_at_utc=None, tool_version="0", schema_version="1")
        with coordinator:
            coordinator.write_header(meta)
            mock_metadata_writer.write_header.assert_called_once_with(meta, coordinator._write_fn)

    def test_write_structure(self, coordinator, mock_structure_writer) -> None:
        entries = [MagicMock(spec=FileEntry)]
        with coordinator:
            coordinator.write_structure(entries)
            mock_structure_writer.write_structure.assert_called_once_with(entries, coordinator._write_fn)

    def test_write_files_open(self, coordinator, mock_section_writer) -> None:
        with coordinator:
            coordinator.write_files_open("full")
            mock_section_writer.write_files_open.assert_called_once_with("full", coordinator._write_fn)

    def test_write_file(self, coordinator, mock_content_writer) -> None:
        entry = MagicMock(spec=FileEntry)
        payload = TextPayload(text="test")
        with coordinator:
            coordinator.write_file(entry, payload, token_count=42)
            mock_content_writer.write_file.assert_called_once_with(entry, payload, coordinator._write_fn, 42)

    def test_write_statistics(self, coordinator, mock_metadata_writer) -> None:
        stats = TokenStats(total_tokens=100)
        with coordinator:
            coordinator.write_statistics(stats)
            mock_metadata_writer.write_statistics.assert_called_once_with(stats, coordinator._write_fn)

    def test_write_footer(self, coordinator, mock_metadata_writer) -> None:
        with coordinator:
            coordinator.write_footer()
            mock_metadata_writer.write_footer.assert_called_once_with(coordinator._write_fn)

    def test_write_files_close(self, coordinator, mock_section_writer) -> None:
        with coordinator:
            coordinator.write_files_close()
            mock_section_writer.write_files_close.assert_called_once_with(coordinator._write_fn)

    def test_write_without_context_raises(self, coordinator) -> None:
        with pytest.raises(RuntimeError, match="not opened"):
            coordinator.write_header(MagicMock())

    def test_close_handles_errors(self, coordinator) -> None:
        # Manually set up a mock to simulate error on flush
        coordinator._text_wrapper = MagicMock()
        coordinator._text_wrapper.flush.side_effect = OSError("flush failed")
        coordinator._stream = MagicMock()

        coordinator.close()
        assert coordinator._stream is None
        assert coordinator._text_wrapper is None
        assert coordinator._buffered_writer is None