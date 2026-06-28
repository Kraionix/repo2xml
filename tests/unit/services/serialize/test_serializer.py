# tests/unit/services/serialize/test_serializer.py
"""Unit tests for XMLSerializer."""

import xml.etree.ElementTree as ET
from io import StringIO
from pathlib import Path
from typing import List, Optional

import pytest

from repo2xml.domain.model import (
    BinaryBase64Payload,
    BinaryHashPayload,
    ErrorCode,
    ErrorPayload,
    ExportMeta,
    FileEntry,
    LinkPayload,
    MetadataPayload,
    SkipCode,
    SkippedPayload,
    TextPayload,
    TokenStats,
)
from repo2xml.services.serialize.xml.serializer import XMLSerializer
from repo2xml.services.serialize.xml_utils import cdata


class TestXMLSerializer:
    @pytest.fixture
    def serializer(self) -> XMLSerializer:
        return XMLSerializer(formatting="compact", include_mtime=True, include_size=True)

    @pytest.fixture
    def sample_entry(self) -> FileEntry:
        return FileEntry(
            abs_path=Path("/repo/file.txt"),
            rel_path="file.txt",
            name="file.txt",
            size=1024,
            mtime_ns=1600000000000000000,  # 2020-09-13 12:26:40 UTC
            is_symlink=False,
        )

    @pytest.fixture
    def sample_meta(self) -> ExportMeta:
        return ExportMeta(
            root_path="/repo",
            generated_at_utc="2025-01-01T00:00:00+00:00",
            tool_version="0.4.0",
            schema_version="1.2",
        )

    def _collect_output(self, write_fn) -> str:
        """Helper to capture output from serializer write calls."""
        buf = StringIO()
        write_fn(buf.write)
        return buf.getvalue()

    def test_write_header(self, serializer: XMLSerializer, sample_meta: ExportMeta) -> None:
        output = self._collect_output(lambda w: serializer.write_header(sample_meta, w))
        assert '<?xml version="1.0" encoding="utf-8"?>' in output
        assert "<repository_context" in output
        assert 'version="1.2"' in output
        assert 'tool_version="0.4.0"' in output
        assert "<meta>" in output
        assert "<root_path>/repo</root_path>" in output
        assert "<generated_at_utc>2025-01-01T00:00:00+00:00</generated_at_utc>" in output

    def test_write_footer(self, serializer: XMLSerializer) -> None:
        output = self._collect_output(serializer.write_footer)
        assert output == "</repository_context>\n"

    def test_write_structure(self, serializer: XMLSerializer, sample_entry: FileEntry) -> None:
        entries = [sample_entry]
        output = self._collect_output(lambda w: serializer.write_structure(entries, w))
        assert "<project_structure>" in output
        assert '<file name="file.txt" path="file.txt"' in output
        assert 'size="1024"' not in output
        assert 'mtime_utc' not in output
        assert "/>" in output

    def test_write_files_open_close(self, serializer: XMLSerializer) -> None:
        output_open = self._collect_output(lambda w: serializer.write_files_open("full", w))
        assert '<files mode="full">' in output_open
        output_close = self._collect_output(serializer.write_files_close)
        assert "</files>" in output_close

    def test_write_metadata(self, serializer: XMLSerializer, sample_entry: FileEntry) -> None:
        payload = MetadataPayload()
        output = self._collect_output(lambda w: serializer.write_file(sample_entry, payload, w))
        assert '<file path="file.txt"' in output
        assert 'ext=".txt"' in output
        assert 'size="1024"' in output
        assert 'mtime_utc="2020-09-13T12:26:40+00:00"' in output
        assert "/>" in output
        assert "tokens" not in output

    def test_write_text(self, serializer: XMLSerializer, sample_entry: FileEntry) -> None:
        payload = TextPayload(text="Hello, world!", encoding="utf-8")
        output = self._collect_output(lambda w: serializer.write_file(sample_entry, payload, w, token_count=42))
        assert '<file path="file.txt"' in output
        assert 'tokens="42"' in output
        assert '<content encoding="utf-8" decode_errors="replace">' in output
        assert cdata("Hello, world!") in output

    def test_write_binary_base64(self, serializer: XMLSerializer, sample_entry: FileEntry) -> None:
        payload = BinaryBase64Payload(chunks=["YWJj", "ZGVm"])
        output = self._collect_output(lambda w: serializer.write_file(sample_entry, payload, w))
        assert 'binary="true"' in output
        assert '<content encoding="base64">' in output
        assert "YWJjZGVm" in output

    def test_write_binary_hash(self, serializer: XMLSerializer, sample_entry: FileEntry) -> None:
        payload = BinaryHashPayload(sha256_hex="abc123")
        output = self._collect_output(lambda w: serializer.write_file(sample_entry, payload, w))
        assert 'binary="true"' in output
        assert '<content encoding="sha256">abc123</content>' in output

    def test_write_link(self, serializer: XMLSerializer) -> None:
        sym_entry = FileEntry(
            abs_path=Path("/repo/link"),
            rel_path="link",
            name="link",
            size=0,
            mtime_ns=0,
            is_symlink=True,
            symlink_target="/some/target",
        )
        payload = LinkPayload(link_target="/some/target")
        output = self._collect_output(lambda w: serializer.write_file(sym_entry, payload, w))
        assert 'link_only="true"' in output
        assert 'link_target="/some/target"' in output

    def test_write_skipped(self, serializer: XMLSerializer, sample_entry: FileEntry) -> None:
        payload = SkippedPayload(code=SkipCode.text_size_limit, message="Too large", detail={"size": 2000})
        output = self._collect_output(lambda w: serializer.write_file(sample_entry, payload, w))
        assert 'skipped="true"' in output
        assert 'skip_code="text_size_limit"' in output
        assert "<error>Too large</error>" in output
        assert "<detail>" in output

    def test_write_error(self, serializer: XMLSerializer, sample_entry: FileEntry) -> None:
        payload = ErrorPayload(code=ErrorCode.text_read_error, message="Read failed", detail={"os_error": "permission"})
        output = self._collect_output(lambda w: serializer.write_file(sample_entry, payload, w))
        assert 'skipped="true"' in output
        assert 'error_code="text_read_error"' in output
        assert "<error>Read failed</error>" in output
        assert "<detail>" in output

    def test_write_statistics(self, serializer: XMLSerializer) -> None:
        stats = TokenStats(total_tokens=12345, files_processed=10)
        output = self._collect_output(lambda w: serializer.write_statistics(stats, w))
        assert '<statistics total_tokens="12345" />' in output

    def test_write_statistics_none(self, serializer: XMLSerializer) -> None:
        output = self._collect_output(lambda w: serializer.write_statistics(None, w))
        assert output == ""

    def test_write_file_dispatch(self, serializer: XMLSerializer, sample_entry: FileEntry) -> None:
        payload = TextPayload(text="test", encoding="utf-8")
        output = self._collect_output(lambda w: serializer.write_file(sample_entry, payload, w, token_count=5))
        assert 'tokens="5"' in output
        assert "test" in output

    def test_formatting_pretty(self) -> None:
        serializer = XMLSerializer(formatting="pretty")
        meta = ExportMeta(root_path="/", generated_at_utc=None, tool_version="0", schema_version="1.2")
        output = self._collect_output(lambda w: serializer.write_header(meta, w))
        assert "\n" in output
        assert "\t" in output

    def test_formatting_minify(self) -> None:
        serializer = XMLSerializer(formatting="minify")
        meta = ExportMeta(root_path="/", generated_at_utc=None, tool_version="0", schema_version="1.2")
        output = self._collect_output(lambda w: serializer.write_header(meta, w))
        assert "\t" not in output

    def test_no_mtime(self) -> None:
        serializer = XMLSerializer(include_mtime=False)
        entry = FileEntry(
            abs_path=Path("/a"),
            rel_path="a",
            name="a",
            size=0,
            mtime_ns=123,
            is_symlink=False,
        )
        payload = MetadataPayload()
        output = self._collect_output(lambda w: serializer.write_file(entry, payload, w))
        assert 'mtime_utc' not in output

    def test_no_size(self) -> None:
        serializer = XMLSerializer(include_size=False)
        entry = FileEntry(
            abs_path=Path("/a"),
            rel_path="a",
            name="a",
            size=100,
            mtime_ns=0,
            is_symlink=False,
        )
        payload = MetadataPayload()
        output = self._collect_output(lambda w: serializer.write_file(entry, payload, w))
        assert 'size' not in output

    def test_text_without_encoding(self) -> None:
        serializer = XMLSerializer()
        entry = FileEntry(abs_path=Path("/a"), rel_path="a", name="a", size=0, mtime_ns=0, is_symlink=False)
        payload = TextPayload(text="hello", encoding=None)
        output = self._collect_output(lambda w: serializer.write_file(entry, payload, w))
        assert '<content decode_errors="replace">' in output
        assert 'encoding' not in output