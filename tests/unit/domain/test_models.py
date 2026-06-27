# tests/unit/domain/test_models.py
"""Unit tests for domain models (data structures)."""

from pathlib import Path
from typing import Iterator

import pytest

from repo2xml.domain.model import (
    BinaryBase64Payload,
    BinaryHashPayload,
    ClassificationResult,
    ErrorCode,
    ErrorInfo,
    ErrorPayload,
    ExportMeta,
    ExportStats,
    FileEntry,
    FilePayload,
    LinkPayload,
    MetadataPayload,
    ParsedRepository,
    RestoreEntry,
    RestoreMeta,
    RestoreStats,
    SkipCode,
    SkipInfo,
    SkippedPayload,
    TextPayload,
    TextReadResult,
    TokenStats,
)


class TestFileEntry:
    def test_creation(self) -> None:
        entry = FileEntry(
            abs_path=Path("/a/b/file.txt"),
            rel_path="a/b/file.txt",
            name="file.txt",
            size=100,
            mtime_ns=1234567890,
            is_symlink=False,
            symlink_target=None,
            token_count=None,
        )
        assert entry.abs_path == Path("/a/b/file.txt")
        assert entry.rel_path == "a/b/file.txt"
        assert entry.name == "file.txt"
        assert entry.size == 100
        assert entry.mtime_ns == 1234567890
        assert entry.is_symlink is False
        assert entry.symlink_target is None
        assert entry.token_count is None

    @pytest.mark.parametrize(
        ("name", "expected_ext"),
        [
            ("file.txt", ".txt"),
            ("archive.tar.gz", ".tar.gz"),
            ("no_ext", ""),
            (".hidden", ""),
            ("file.py", ".py"),
            ("test.json", ".json"),
        ],
    )
    def test_ext_property(self, name: str, expected_ext: str) -> None:
        entry = FileEntry(
            abs_path=Path("/dummy"),
            rel_path=name,
            name=name,
            size=0,
            mtime_ns=0,
            is_symlink=False,
        )
        assert entry.ext == expected_ext


class TestExportMeta:
    def test_creation(self) -> None:
        meta = ExportMeta(
            root_path="/repo",
            generated_at_utc="2025-01-01T00:00:00Z",
            tool_version="0.4.0",
            schema_version="1.2",
        )
        assert meta.root_path == "/repo"
        assert meta.generated_at_utc == "2025-01-01T00:00:00Z"
        assert meta.tool_version == "0.4.0"
        assert meta.schema_version == "1.2"


class TestRestoreMeta:
    def test_creation(self) -> None:
        meta = RestoreMeta(
            target_root="/output",
            restored_at_utc="2025-01-01T00:00:00Z",
            source_document="context.xml",
        )
        assert meta.target_root == "/output"
        assert meta.restored_at_utc == "2025-01-01T00:00:00Z"
        assert meta.source_document == "context.xml"

    def test_source_document_optional(self) -> None:
        meta = RestoreMeta(
            target_root="/output",
            restored_at_utc="2025-01-01T00:00:00Z",
            source_document=None,
        )
        assert meta.source_document is None


class TestSkipCode:
    def test_values(self) -> None:
        assert SkipCode.binary_skip_mode == "binary_skip_mode"
        assert SkipCode.text_size_limit == "text_size_limit"
        assert SkipCode.base64_size_limit == "base64_size_limit"
        assert SkipCode.hash_size_limit == "hash_size_limit"
        assert SkipCode.unknown == "unknown"

    def test_from_string(self) -> None:
        assert SkipCode("binary_skip_mode") == SkipCode.binary_skip_mode
        with pytest.raises(ValueError):
            SkipCode("invalid")


class TestErrorCode:
    def test_values(self) -> None:
        assert ErrorCode.sniff_read_error == "sniff_read_error"
        assert ErrorCode.stat_error == "stat_error"
        assert ErrorCode.text_read_error == "text_read_error"
        assert ErrorCode.text_decode_error == "text_decode_error"
        assert ErrorCode.binary_detected == "binary_detected"
        assert ErrorCode.binary_hash_error == "binary_hash_error"
        assert ErrorCode.base64_error == "base64_error"
        assert ErrorCode.processor_error == "processor_error"
        assert ErrorCode.unknown == "unknown"

    def test_from_string(self) -> None:
        assert ErrorCode("stat_error") == ErrorCode.stat_error
        with pytest.raises(ValueError):
            ErrorCode("invalid")


class TestSkipInfo:
    def test_creation(self) -> None:
        info = SkipInfo(code=SkipCode.text_size_limit, detail={"size": 1000, "limit": 500})
        assert info.code == SkipCode.text_size_limit
        assert info.detail == {"size": 1000, "limit": 500}

    def test_empty_detail(self) -> None:
        info = SkipInfo(code=SkipCode.unknown)
        assert info.detail == {}


class TestErrorInfo:
    def test_creation(self) -> None:
        info = ErrorInfo(code=ErrorCode.text_decode_error, detail={"encoding": "utf-8"})
        assert info.code == ErrorCode.text_decode_error
        assert info.detail == {"encoding": "utf-8"}

    def test_empty_detail(self) -> None:
        info = ErrorInfo(code=ErrorCode.unknown)
        assert info.detail == {}


class TestTokenStats:
    def test_defaults(self) -> None:
        stats = TokenStats()
        assert stats.total_tokens == 0
        assert stats.files_processed == 0
        assert stats.files_skipped == 0
        assert stats.tokens_by_extension == {}
        assert stats.max_tokens == 0
        assert stats.min_tokens == 0
        assert stats.errors == 0

    def test_update(self) -> None:
        stats = TokenStats()
        stats.total_tokens = 100
        stats.files_processed = 5
        stats.tokens_by_extension[".py"] = 100
        assert stats.total_tokens == 100
        assert stats.files_processed == 5
        assert stats.tokens_by_extension == {".py": 100}


class TestExportStats:
    def test_creation(self) -> None:
        stats = ExportStats(
            files_total=10,
            files_emitted=8,
            files_skipped=1,
            files_errors=1,
            skipped_by_code={"text_size_limit": 1},
            errors_by_code={"stat_error": 1},
            scan_warning_summary="some warnings",
            redaction_stats=None,
            classification_stats=None,
            token_stats=TokenStats(),
        )
        assert stats.files_total == 10
        assert stats.files_emitted == 8
        assert stats.files_skipped == 1
        assert stats.files_errors == 1
        assert stats.skipped_by_code == {"text_size_limit": 1}
        assert stats.errors_by_code == {"stat_error": 1}
        assert stats.scan_warning_summary == "some warnings"
        assert stats.redaction_stats is None
        assert stats.classification_stats is None
        assert isinstance(stats.token_stats, TokenStats)

    def test_optional_fields_none(self) -> None:
        stats = ExportStats(
            files_total=0,
            files_emitted=0,
            files_skipped=0,
            files_errors=0,
        )
        assert stats.scan_warning_summary is None
        assert stats.redaction_stats is None
        assert stats.classification_stats is None
        assert stats.token_stats is None


class TestRestoreStats:
    def test_creation(self) -> None:
        stats = RestoreStats(
            files_total=5,
            files_created=3,
            files_skipped=1,
            files_errors=1,
            dirs_created=2,
            symlinks_created=0,
            skipped_by_code={"no_content": 1},
            errors_by_code={"RestoreError": 1},
        )
        assert stats.files_total == 5
        assert stats.files_created == 3
        assert stats.files_skipped == 1
        assert stats.files_errors == 1
        assert stats.dirs_created == 2
        assert stats.symlinks_created == 0
        assert stats.skipped_by_code == {"no_content": 1}
        assert stats.errors_by_code == {"RestoreError": 1}

    def test_empty_dicts_by_default(self) -> None:
        stats = RestoreStats(
            files_total=0,
            files_created=0,
            files_skipped=0,
            files_errors=0,
            dirs_created=0,
            symlinks_created=0,
        )
        assert stats.skipped_by_code == {}
        assert stats.errors_by_code == {}


class TestPayloads:
    def test_metadata_payload(self) -> None:
        p = MetadataPayload()
        assert isinstance(p, FilePayload)

    def test_link_payload(self) -> None:
        p = LinkPayload(link_target="/some/link")
        assert p.link_target == "/some/link"

    def test_link_payload_optional_target(self) -> None:
        p = LinkPayload()
        assert p.link_target is None

    def test_text_payload(self) -> None:
        p = TextPayload(text="content", encoding="utf-8")
        assert p.text == "content"
        assert p.encoding == "utf-8"

    def test_binary_hash_payload(self) -> None:
        p = BinaryHashPayload(sha256_hex="abc123")
        assert p.sha256_hex == "abc123"

    def test_binary_base64_payload(self) -> None:
        chunks = ["YWJj", "ZGVm"]
        p = BinaryBase64Payload(chunks=chunks)
        assert list(p.chunks) == chunks

    def test_skipped_payload(self) -> None:
        p = SkippedPayload(code=SkipCode.text_size_limit, message="too large", detail={"size": 1000})
        assert p.code == SkipCode.text_size_limit
        assert p.message == "too large"
        assert p.detail == {"size": 1000}

    def test_error_payload(self) -> None:
        p = ErrorPayload(code=ErrorCode.text_read_error, message="read failed", detail={"os_error": "permission"})
        assert p.code == ErrorCode.text_read_error
        assert p.message == "read failed"
        assert p.detail == {"os_error": "permission"}


class TestRestoreEntry:
    def test_creation(self) -> None:
        entry = FileEntry(
            abs_path=Path("/a"),
            rel_path="a",
            name="a",
            size=0,
            mtime_ns=0,
            is_symlink=False,
        )
        payload = TextPayload(text="hello")
        re = RestoreEntry(entry=entry, payload=payload)
        assert re.entry is entry
        assert re.payload is payload


class TestParsedRepository:
    def test_creation(self) -> None:
        meta = ExportMeta(root_path="/", generated_at_utc=None, tool_version="0", schema_version="1")
        structure: list[FileEntry] = []
        files: Iterator[RestoreEntry] = iter([])
        repo = ParsedRepository(meta=meta, structure=structure, files=files)
        assert repo.meta is meta
        assert repo.structure is structure
        assert repo.files is files


class TestClassificationResult:
    def test_text_kind(self) -> None:
        res = ClassificationResult(kind="text", encoding="utf-8", sample=b"abc")
        assert res.kind == "text"
        assert res.encoding == "utf-8"
        assert res.sample == b"abc"
        assert res.error is None

    def test_binary_kind(self) -> None:
        res = ClassificationResult(kind="binary")
        assert res.kind == "binary"
        assert res.encoding is None
        assert res.sample is None
        assert res.error is None

    def test_error_kind(self) -> None:
        res = ClassificationResult(kind="error", error="read failed")
        assert res.kind == "error"
        assert res.error == "read failed"
        assert res.encoding is None
        assert res.sample is None


class TestTextReadResult:
    def test_text_kind(self) -> None:
        res = TextReadResult(kind="text", text="hello", encoding="utf-8")
        assert res.kind == "text"
        assert res.text == "hello"
        assert res.encoding == "utf-8"
        assert res.skipped is None
        assert res.error is None

    def test_skip_kind(self) -> None:
        info = SkipInfo(code=SkipCode.text_size_limit)
        res = TextReadResult(kind="skip", skipped=info)
        assert res.kind == "skip"
        assert res.skipped is info
        assert res.text is None
        assert res.encoding is None
        assert res.error is None

    def test_error_kind(self) -> None:
        info = ErrorInfo(code=ErrorCode.text_read_error)
        res = TextReadResult(kind="error", error=info)
        assert res.kind == "error"
        assert res.error is info
        assert res.text is None
        assert res.encoding is None
        assert res.skipped is None