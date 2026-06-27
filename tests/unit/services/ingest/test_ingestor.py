# tests/unit/services/ingest/test_ingestor.py
"""Unit tests for StandardIngestor."""

import io
import os
from pathlib import Path
from unittest.mock import MagicMock, mock_open, patch

import pytest

from repo2xml.domain.model import ErrorCode, SkipCode
from repo2xml.services.ingest.ingestor import StandardIngestor


class TestStandardIngestor:
    @pytest.fixture
    def ingestor(self) -> StandardIngestor:
        return StandardIngestor(newline_mode="preserve", decode_errors="replace")

    @pytest.fixture
    def ingestor_lf(self) -> StandardIngestor:
        return StandardIngestor(newline_mode="lf", decode_errors="replace")

    @pytest.fixture
    def ingestor_strict(self) -> StandardIngestor:
        return StandardIngestor(newline_mode="preserve", decode_errors="strict")

    # ------------------------------------------------------------------
    # read_text tests
    # ------------------------------------------------------------------

    def test_read_text_success(self, ingestor: StandardIngestor, tmp_path: Path) -> None:
        path = tmp_path / "file.txt"
        path.write_text("hello world", encoding="utf-8")

        result = ingestor.read_text(path, max_size=1000)
        assert result.kind == "text"
        assert result.text == "hello world"
        assert result.encoding == "utf-8"
        assert result.skipped is None
        assert result.error is None

    def test_read_text_with_sniff_sample(self, ingestor: StandardIngestor, tmp_path: Path) -> None:
        path = tmp_path / "file.txt"
        path.write_text("hello world", encoding="utf-8")

        sample = b"hell"
        result = ingestor.read_text(path, max_size=1000, sniff_sample=sample)
        assert result.kind == "text"
        assert result.text == "hello world"
        assert result.encoding == "utf-8"

    def test_read_text_exceeds_max_size(self, ingestor: StandardIngestor, tmp_path: Path) -> None:
        path = tmp_path / "file.txt"
        path.write_text("x" * 100, encoding="utf-8")

        result = ingestor.read_text(path, max_size=50)
        assert result.kind == "skip"
        assert result.skipped is not None
        assert result.skipped.code == SkipCode.text_size_limit
        assert result.skipped.detail["size"] == 100
        assert result.skipped.detail["limit"] == 50

    def test_read_text_os_error(self, ingestor: StandardIngestor, tmp_path: Path) -> None:
        path = tmp_path / "nonexistent.txt"
        result = ingestor.read_text(path, max_size=1000)
        assert result.kind == "error"
        assert result.error is not None
        assert result.error.code == ErrorCode.stat_error
        # Error message varies by OS; just check it's present
        assert "os_error" in result.error.detail
        assert len(str(result.error.detail["os_error"])) > 0

    def test_read_text_decode_error_strict(self, ingestor_strict: StandardIngestor, tmp_path: Path) -> None:
        path = tmp_path / "binary.bin"
        path.write_bytes(b"\xff\xfe\x00\x00")  # invalid UTF-8

        result = ingestor_strict.read_text(path, max_size=1000)
        assert result.kind == "error"
        assert result.error is not None
        assert result.error.code == ErrorCode.text_decode_error
        # The error message may not contain "UnicodeDecodeError" exactly, but it should contain "invalid start byte"
        detail = str(result.error.detail.get("decode_error", ""))
        assert "invalid start byte" in detail or "UnicodeDecodeError" in detail

    def test_read_text_decode_error_replace(self, ingestor: StandardIngestor, tmp_path: Path) -> None:
        path = tmp_path / "binary.bin"
        path.write_bytes(b"\xff\xfe\x00\x00")

        result = ingestor.read_text(path, max_size=1000)
        assert result.kind == "text"
        assert "\ufffd" in result.text

    def test_read_text_newline_conversion(self, ingestor_lf: StandardIngestor, tmp_path: Path) -> None:
        path = tmp_path / "file.txt"
        # Write raw bytes to avoid platform newline conversions
        path.write_bytes(b"line1\r\nline2\rline3\n")

        result = ingestor_lf.read_text(path, max_size=1000)
        assert result.kind == "text"
        assert result.text == "line1\nline2\nline3\n"

    def test_read_text_with_utf16_bom(self, ingestor: StandardIngestor, tmp_path: Path) -> None:
        path = tmp_path / "file.txt"
        content = b"\xff\xfeh\x00e\x00l\x00l\x00o\x00"
        path.write_bytes(content)

        result = ingestor.read_text(path, max_size=1000)
        assert result.kind == "text"
        # Should decode with utf-8 by default, which will produce replacement chars
        assert "\ufffd" in result.text

    # ------------------------------------------------------------------
    # sha256_file tests
    # ------------------------------------------------------------------

    def test_sha256_file(self, tmp_path: Path) -> None:
        path = tmp_path / "data.bin"
        path.write_bytes(b"hello")
        digest = StandardIngestor.sha256_file(path)
        expected = "2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824"
        assert digest == expected

    def test_sha256_file_empty(self, tmp_path: Path) -> None:
        path = tmp_path / "empty.bin"
        path.write_bytes(b"")
        digest = StandardIngestor.sha256_file(path)
        expected = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
        assert digest == expected

    # ------------------------------------------------------------------
    # iter_base64_chunks tests
    # ------------------------------------------------------------------

    def test_iter_base64_chunks(self, tmp_path: Path) -> None:
        path = tmp_path / "data.bin"
        path.write_bytes(b"abcdef")
        chunks = list(StandardIngestor.iter_base64_chunks(path, chunk_size=3))
        assert "".join(chunks) == "YWJjZGVm"

    def test_iter_base64_chunks_uneven(self, tmp_path: Path) -> None:
        path = tmp_path / "data.bin"
        path.write_bytes(b"abcde")
        chunks = list(StandardIngestor.iter_base64_chunks(path, chunk_size=3))
        assert "".join(chunks) == "YWJjZGU="

    def test_iter_base64_chunks_empty(self, tmp_path: Path) -> None:
        path = tmp_path / "empty.bin"
        path.write_bytes(b"")
        chunks = list(StandardIngestor.iter_base64_chunks(path))
        assert chunks == []

    def test_iter_base64_chunks_large(self, tmp_path: Path) -> None:
        data = b"a" * 100
        path = tmp_path / "data.bin"
        path.write_bytes(data)
        chunks = list(StandardIngestor.iter_base64_chunks(path, chunk_size=10))
        assert len(chunks) > 1
        import base64
        expected = base64.b64encode(data).decode("ascii")
        assert "".join(chunks) == expected