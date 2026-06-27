# tests/unit/services/output/test_targets.py
"""Unit tests for output targets and compression."""

import gzip
import io
import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from repo2xml.domain.exceptions import OutputError
from repo2xml.services.output.targets import (
    ClipboardTarget,
    CompressMode,
    DevNullTarget,
    FileTarget,
    StdoutTarget,
    open_output_stream,
)


class TestOpenOutputStream:
    def test_stdout_no_compress(self, monkeypatch) -> None:
        mock_buffer = MagicMock()
        monkeypatch.setattr(sys, "stdout", MagicMock(buffer=mock_buffer))
        stream, closer = open_output_stream(
            output_path=Path("out"), use_stdout=True, compress=CompressMode.none
        )
        assert stream is mock_buffer
        closer()  # no-op

    def test_stdout_gzip(self, monkeypatch) -> None:
        mock_buffer = MagicMock()
        monkeypatch.setattr(sys, "stdout", MagicMock(buffer=mock_buffer))
        with patch("gzip.GzipFile") as mock_gzip:
            mock_gzip.return_value = MagicMock()
            stream, closer = open_output_stream(
                output_path=Path("out"), use_stdout=True, compress=CompressMode.gzip
            )
            mock_gzip.assert_called_once_with(fileobj=mock_buffer, mode="wb")
            closer()

    def test_stdout_zstd_missing_dependency(self, monkeypatch) -> None:
        mock_buffer = MagicMock()
        monkeypatch.setattr(sys, "stdout", MagicMock(buffer=mock_buffer))
        with patch("builtins.__import__", side_effect=ImportError("no zstd")):
            with pytest.raises(OutputError, match="zstd compression requires"):
                open_output_stream(
                    output_path=Path("out"), use_stdout=True, compress=CompressMode.zstd
                )

    def test_stdout_zstd(self, monkeypatch) -> None:
        mock_buffer = MagicMock()
        monkeypatch.setattr(sys, "stdout", MagicMock(buffer=mock_buffer))
        mock_zstd = MagicMock()
        mock_zstd.ZstdCompressor.return_value.stream_writer.return_value = MagicMock()
        with patch.dict("sys.modules", {"zstandard": mock_zstd}):
            stream, closer = open_output_stream(
                output_path=Path("out"), use_stdout=True, compress=CompressMode.zstd
            )
            closer()

    def test_file_no_compress(self, tmp_path: Path) -> None:
        out_path = tmp_path / "out.txt"
        stream, closer = open_output_stream(
            output_path=out_path, use_stdout=False, compress=CompressMode.none
        )
        assert stream is not None
        stream.write(b"test")
        closer()
        assert out_path.read_bytes() == b"test"

    def test_file_gzip(self, tmp_path: Path) -> None:
        out_path = tmp_path / "out.gz"
        stream, closer = open_output_stream(
            output_path=out_path, use_stdout=False, compress=CompressMode.gzip
        )
        stream.write(b"test")
        closer()
        with gzip.open(out_path, "rb") as f:
            assert f.read() == b"test"

    def test_file_zstd_missing_dependency(self, tmp_path: Path) -> None:
        out_path = tmp_path / "out.zst"
        with patch("builtins.__import__", side_effect=ImportError("no zstd")):
            with pytest.raises(OutputError, match="zstd compression requires"):
                open_output_stream(
                    output_path=out_path, use_stdout=False, compress=CompressMode.zstd
                )

    def test_file_zstd(self, tmp_path: Path) -> None:
        out_path = tmp_path / "out.zst"
        mock_zstd = MagicMock()
        mock_zstd.ZstdCompressor.return_value.stream_writer.return_value = MagicMock()
        with patch.dict("sys.modules", {"zstandard": mock_zstd}):
            stream, closer = open_output_stream(
                output_path=out_path, use_stdout=False, compress=CompressMode.zstd
            )
            stream.write(b"test")
            closer()

    def test_file_parent_mkdir(self, tmp_path: Path) -> None:
        out_path = tmp_path / "sub" / "out.txt"
        stream, closer = open_output_stream(
            output_path=out_path, use_stdout=False, compress=CompressMode.none
        )
        closer()
        assert out_path.parent.exists()


class TestFileTarget:
    def test_open(self, tmp_path: Path) -> None:
        target = FileTarget(tmp_path / "file.txt")
        with target.open() as stream:
            stream.write(b"data")
        assert (tmp_path / "file.txt").read_bytes() == b"data"

    def test_describe(self) -> None:
        target = FileTarget(Path("/tmp/file.txt"))
        # On Windows, path may use backslashes; just check it starts with file://
        desc = target.describe()
        assert desc.startswith("file://")
        assert "file.txt" in desc


class TestStdoutTarget:
    def test_open(self, monkeypatch) -> None:
        mock_buffer = MagicMock()
        monkeypatch.setattr(sys, "stdout", MagicMock(buffer=mock_buffer))
        target = StdoutTarget(compress=CompressMode.none)
        with target.open() as stream:
            stream.write(b"hello")
        mock_buffer.write.assert_called_once_with(b"hello")

    def test_describe(self) -> None:
        target = StdoutTarget()
        assert target.describe() == "stdout"


class TestClipboardTarget:
    def test_open(self) -> None:
        target = ClipboardTarget()
        mock_pyperclip = MagicMock()
        with patch.dict("sys.modules", {"pyperclip": mock_pyperclip}):
            with target.open() as stream:
                stream.write(b"clipboard content")
            mock_pyperclip.copy.assert_called_once_with("clipboard content")

    def test_missing_dependency(self) -> None:
        target = ClipboardTarget()
        with patch("builtins.__import__", side_effect=ImportError("no pyperclip")):
            with pytest.raises(OutputError, match="Clipboard support requires"):
                with target.open():
                    pass

    def test_pyperclip_exception(self) -> None:
        target = ClipboardTarget()
        mock_pyperclip = MagicMock()
        # Define PyperclipException as a subclass of Exception on the mock
        class PyperclipException(Exception):
            pass
        mock_pyperclip.PyperclipException = PyperclipException
        mock_pyperclip.copy.side_effect = PyperclipException("clipboard error")
        with patch.dict("sys.modules", {"pyperclip": mock_pyperclip}):
            with pytest.raises(OutputError, match="Clipboard error"):
                with target.open() as stream:
                    stream.write(b"data")


class TestDevNullTarget:
    def test_open(self) -> None:
        target = DevNullTarget()
        with target.open() as stream:
            stream.write(b"should be ignored")
        # No assertion, just ensure it doesn't crash
        # describe uses os.devnull, which is "nul" on Windows
        assert target.describe() == f"file://{os.devnull}"

    def test_describe(self) -> None:
        target = DevNullTarget()
        assert target.describe() == f"file://{os.devnull}"