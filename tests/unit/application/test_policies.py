# tests/unit/application/test_policies.py
"""Unit tests for ExportPayloadBuilder and ReasonFormatter."""

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from repo2xml.application.policies import ExportPayloadBuilder, ReasonFormatter
from repo2xml.domain.model import (
    ClassificationResult,
    ErrorCode,
    ErrorInfo,
    ErrorPayload,
    FileEntry,
    MetadataPayload,
    SkipCode,
    SkipInfo,
    TextPayload,
)


class TestReasonFormatter:
    def test_format_skip(self) -> None:
        info = SkipInfo(code=SkipCode.binary_skip_mode)
        assert ReasonFormatter.format_skip(info) == "Skipped: Binary file detected (binary mode: skip)"

        info = SkipInfo(code=SkipCode.text_size_limit, detail={"size": 100, "limit": 50})
        assert ReasonFormatter.format_skip(info) == "Skipped: File size 100 exceeds text limit 50"

        info = SkipInfo(code=SkipCode.base64_size_limit, detail={"size": 200, "limit": 100})
        assert ReasonFormatter.format_skip(info) == "Skipped: File size 200 exceeds base64 limit 100"

        info = SkipInfo(code=SkipCode.hash_size_limit, detail={"size": 300, "limit": 150})
        assert ReasonFormatter.format_skip(info) == "Skipped: File size 300 exceeds hash limit 150"

        info = SkipInfo(code=SkipCode.unknown)
        assert ReasonFormatter.format_skip(info) == "Skipped"

    def test_format_error(self) -> None:
        info = ErrorInfo(code=ErrorCode.sniff_read_error, detail={"os_error": "permission"})
        assert ReasonFormatter.format_error(info) == "Error reading file sample: permission"

        info = ErrorInfo(code=ErrorCode.stat_error, detail={"os_error": "not found"})
        assert ReasonFormatter.format_error(info) == "Error stat file: not found"

        info = ErrorInfo(code=ErrorCode.text_read_error, detail={"os_error": "io error"})
        assert ReasonFormatter.format_error(info) == "Error reading file: io error"

        info = ErrorInfo(code=ErrorCode.text_decode_error, detail={"encoding": "utf-8", "decode_error": "invalid"})
        assert ReasonFormatter.format_error(info) == "Error decoding with utf-8: invalid"

        info = ErrorInfo(code=ErrorCode.binary_hash_error, detail={"os_error": "hash fail"})
        assert ReasonFormatter.format_error(info) == "Error hashing file: hash fail"

        info = ErrorInfo(code=ErrorCode.base64_error, detail={"os_error": "base64 fail"})
        assert ReasonFormatter.format_error(info) == "Error base64-encoding file: base64 fail"

        info = ErrorInfo(code=ErrorCode.processor_error, detail={"processor_error": "unexpected"})
        assert ReasonFormatter.format_error(info) == "Text processor error: unexpected"

        info = ErrorInfo(code=ErrorCode.unknown)
        assert ReasonFormatter.format_error(info) == "Error"


class TestExportPayloadBuilder:
    @pytest.fixture
    def entry(self) -> FileEntry:
        return FileEntry(
            abs_path=Path("/repo/file.txt"),
            rel_path="file.txt",
            name="file.txt",
            size=100,
            mtime_ns=0,
            is_symlink=False,
        )

    def test_first_matching_policy_wins(self, entry: FileEntry) -> None:
        mock_policy1 = MagicMock()
        mock_policy1.apply.return_value = MetadataPayload()

        mock_policy2 = MagicMock()
        mock_policy2.apply.return_value = TextPayload(text="should not be used", encoding="utf-8")

        builder = ExportPayloadBuilder([mock_policy1, mock_policy2])
        classification = ClassificationResult(kind="text", encoding="utf-8")
        payload = builder.build(entry, classification)

        assert isinstance(payload, MetadataPayload)
        mock_policy1.apply.assert_called_once_with(entry, classification)
        mock_policy2.apply.assert_not_called()

    def test_skip_policies_until_match(self, entry: FileEntry) -> None:
        mock_policy1 = MagicMock()
        mock_policy1.apply.return_value = None

        mock_policy2 = MagicMock()
        mock_policy2.apply.return_value = TextPayload(text="matched", encoding="utf-8")

        builder = ExportPayloadBuilder([mock_policy1, mock_policy2])
        classification = ClassificationResult(kind="text", encoding="utf-8")
        payload = builder.build(entry, classification)

        assert isinstance(payload, TextPayload)
        assert payload.text == "matched"
        mock_policy1.apply.assert_called_once_with(entry, classification)
        mock_policy2.apply.assert_called_once_with(entry, classification)

    def test_fallback_when_no_policy_matches(self, entry: FileEntry) -> None:
        mock_policy = MagicMock()
        mock_policy.apply.return_value = None

        builder = ExportPayloadBuilder([mock_policy])
        classification = ClassificationResult(kind="text", encoding="utf-8")
        payload = builder.build(entry, classification)

        assert isinstance(payload, ErrorPayload)
        assert payload.code == ErrorCode.unknown
        assert "No policy matched" in payload.message
        mock_policy.apply.assert_called_once_with(entry, classification)

    def test_empty_policy_list_returns_fallback(self, entry: FileEntry) -> None:
        builder = ExportPayloadBuilder([])
        classification = ClassificationResult(kind="text", encoding="utf-8")
        payload = builder.build(entry, classification)

        assert isinstance(payload, ErrorPayload)
        assert payload.code == ErrorCode.unknown
        assert "No policy matched" in payload.message