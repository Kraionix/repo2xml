# tests/unit/services/serialize/test_document_writer.py
"""Unit tests for XMLDocumentWriter (formerly XMLSerializer)."""

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
from repo2xml.services.serialize.xml.document_writer import XMLDocumentWriter
from repo2xml.services.serialize.xml_utils import cdata


class TestXMLDocumentWriter:
    @pytest.fixture
    def writer(self) -> XMLDocumentWriter:
        # We'll pass a dummy write_fn, but in tests we'll use _collect_output to capture.
        # The writer expects write_fn in constructor.
        # We'll create a writer with a dummy and then override _write in each test.
        # Better: we can create the writer without write_fn and set it later, but our implementation
        # requires write_fn. We'll just create with a lambda that captures output.
        def dummy(s): pass
        return XMLDocumentWriter(
            formatting="compact",
            include_mtime=True,
            include_size=True,
            text_decode_errors="replace",
            write_fn=dummy,
        )

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

    def _collect_output(self, writer: XMLDocumentWriter, func) -> str:
        """Helper to capture output from writer calls."""
        buf = StringIO()
        # Override the _write method to write to buf
        original_write = writer._write
        writer._write = buf.write
        try:
            func()
        finally:
            writer._write = original_write
        return buf.getvalue()

    def test_begin_document(self, writer: XMLDocumentWriter, sample_meta: ExportMeta) -> None:
        output = self._collect_output(writer, lambda: writer.begin_document(sample_meta))
        assert '<?xml version="1.0" encoding="utf-8"?>' in output
        assert "<repository_context" in output
        assert 'version="1.2"' in output
        assert 'tool_version="0.4.0"' in output
        assert "<meta>" in output
        assert "<root_path>/repo</root_path>" in output
        assert "<generated_at_utc>2025-01-01T00:00:00+00:00</generated_at_utc>" in output

    def test_end_document(self, writer: XMLDocumentWriter) -> None:
        output = self._collect_output(writer, writer.end_document)
        assert output == "</repository_context>\n"

    def test_write_structure(self, writer: XMLDocumentWriter, sample_entry: FileEntry) -> None:
        entries = [sample_entry]
        output = self._collect_output(writer, lambda: writer.write_structure(entries))
        assert "<project_structure>" in output
        assert '<file name="file.txt" path="file.txt"' in output
        assert 'size="1024"' not in output
        assert 'mtime_utc' not in output
        assert "/>" in output

    def test_begin_files_section_end_files_section(self, writer: XMLDocumentWriter) -> None:
        output_open = self._collect_output(writer, lambda: writer.begin_files_section("full"))
        assert '<files mode="full">' in output_open
        output_close = self._collect_output(writer, writer.end_files_section)
        assert "</files>" in output_close

    def test_write_file_metadata(self, writer: XMLDocumentWriter, sample_entry: FileEntry) -> None:
        payload = MetadataPayload()
        output = self._collect_output(writer, lambda: writer.write_file(sample_entry, payload))
        assert '<file path="file.txt"' in output
        assert 'ext=".txt"' in output
        assert 'size="1024"' in output
        assert 'mtime_utc="2020-09-13T12:26:40+00:00"' in output
        assert "/>" in output
        assert "tokens" not in output

    def test_write_file_text(self, writer: XMLDocumentWriter, sample_entry: FileEntry) -> None:
        payload = TextPayload(text="Hello, world!", encoding="utf-8")
        output = self._collect_output(writer, lambda: writer.write_file(sample_entry, payload, token_count=42))
        assert '<file path="file.txt"' in output
        assert 'tokens="42"' in output
        assert '<content encoding="utf-8" decode_errors="replace">' in output
        assert cdata("Hello, world!") in output

    def test_write_file_binary_base64(self, writer: XMLDocumentWriter, sample_entry: FileEntry) -> None:
        payload = BinaryBase64Payload(chunks=["YWJj", "ZGVm"])
        output = self._collect_output(writer, lambda: writer.write_file(sample_entry, payload))
        assert 'binary="true"' in output
        assert '<content encoding="base64">' in output
        assert "YWJjZGVm" in output

    def test_write_file_binary_hash(self, writer: XMLDocumentWriter, sample_entry: FileEntry) -> None:
        payload = BinaryHashPayload(sha256_hex="abc123")
        output = self._collect_output(writer, lambda: writer.write_file(sample_entry, payload))
        assert 'binary="true"' in output
        assert '<content encoding="sha256">abc123</content>' in output

    def test_write_file_link(self, writer: XMLDocumentWriter) -> None:
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
        output = self._collect_output(writer, lambda: writer.write_file(sym_entry, payload))
        assert 'link_only="true"' in output
        assert 'link_target="/some/target"' in output

    def test_write_file_skipped(self, writer: XMLDocumentWriter, sample_entry: FileEntry) -> None:
        payload = SkippedPayload(code=SkipCode.text_size_limit, message="Too large", detail={"size": 2000})
        output = self._collect_output(writer, lambda: writer.write_file(sample_entry, payload))
        assert 'skipped="true"' in output
        assert 'skip_code="text_size_limit"' in output
        assert "<error>Too large</error>" in output
        assert "<detail>" in output

    def test_write_file_error(self, writer: XMLDocumentWriter, sample_entry: FileEntry) -> None:
        payload = ErrorPayload(code=ErrorCode.text_read_error, message="Read failed", detail={"os_error": "permission"})
        output = self._collect_output(writer, lambda: writer.write_file(sample_entry, payload))
        assert 'skipped="true"' in output
        assert 'error_code="text_read_error"' in output
        assert "<error>Read failed</error>" in output
        assert "<detail>" in output

    def test_write_statistics(self, writer: XMLDocumentWriter) -> None:
        stats = TokenStats(total_tokens=12345, files_processed=10)
        output = self._collect_output(writer, lambda: writer.write_statistics(stats))
        assert '<statistics total_tokens="12345" />' in output

    def test_write_statistics_none(self, writer: XMLDocumentWriter) -> None:
        output = self._collect_output(writer, lambda: writer.write_statistics(None))
        assert output == ""

    def test_formatting_pretty(self) -> None:
        writer = XMLDocumentWriter(
            formatting="pretty",
            include_mtime=True,
            include_size=True,
            text_decode_errors="replace",
            write_fn=lambda s: None,
        )
        meta = ExportMeta(root_path="/", generated_at_utc=None, tool_version="0", schema_version="1.2")
        output = self._collect_output(writer, lambda: writer.begin_document(meta))
        assert "\n" in output
        assert "\t" in output

    def test_formatting_minify(self) -> None:
        writer = XMLDocumentWriter(
            formatting="minify",
            include_mtime=True,
            include_size=True,
            text_decode_errors="replace",
            write_fn=lambda s: None,
        )
        meta = ExportMeta(root_path="/", generated_at_utc=None, tool_version="0", schema_version="1.2")
        output = self._collect_output(writer, lambda: writer.begin_document(meta))
        assert "\t" not in output

    def test_no_mtime(self) -> None:
        writer = XMLDocumentWriter(
            formatting="compact",
            include_mtime=False,
            include_size=True,
            text_decode_errors="replace",
            write_fn=lambda s: None,
        )
        entry = FileEntry(
            abs_path=Path("/a"),
            rel_path="a",
            name="a",
            size=0,
            mtime_ns=123,
            is_symlink=False,
        )
        payload = MetadataPayload()
        output = self._collect_output(writer, lambda: writer.write_file(entry, payload))
        assert 'mtime_utc' not in output

    def test_no_size(self) -> None:
        writer = XMLDocumentWriter(
            formatting="compact",
            include_mtime=True,
            include_size=False,
            text_decode_errors="replace",
            write_fn=lambda s: None,
        )
        entry = FileEntry(
            abs_path=Path("/a"),
            rel_path="a",
            name="a",
            size=100,
            mtime_ns=0,
            is_symlink=False,
        )
        payload = MetadataPayload()
        output = self._collect_output(writer, lambda: writer.write_file(entry, payload))
        assert 'size' not in output

    def test_text_without_encoding(self) -> None:
        writer = XMLDocumentWriter(
            formatting="compact",
            include_mtime=True,
            include_size=True,
            text_decode_errors="replace",
            write_fn=lambda s: None,
        )
        entry = FileEntry(abs_path=Path("/a"), rel_path="a", name="a", size=0, mtime_ns=0, is_symlink=False)
        payload = TextPayload(text="hello", encoding=None)
        output = self._collect_output(writer, lambda: writer.write_file(entry, payload))
        assert '<content decode_errors="replace">' in output
        assert 'encoding' not in output