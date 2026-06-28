# tests/unit/services/policies/test_error_policy.py
"""Unit tests for ErrorPolicy."""

from pathlib import Path

import pytest

from repo2xml.domain.model import ClassificationResult, ErrorCode, ErrorPayload, FileEntry
from repo2xml.services.policies import ErrorPolicy


class TestErrorPolicy:
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

    def test_error_kind_returns_error_payload(self, entry: FileEntry) -> None:
        classification = ClassificationResult(kind="error", error="read failed")
        policy = ErrorPolicy()
        payload = policy.apply(entry, classification)
        assert isinstance(payload, ErrorPayload)
        assert payload.code == ErrorCode.sniff_read_error
        assert "read failed" in payload.message

    def test_text_kind_returns_none(self, entry: FileEntry) -> None:
        classification = ClassificationResult(kind="text", encoding="utf-8")
        policy = ErrorPolicy()
        payload = policy.apply(entry, classification)
        assert payload is None

    def test_binary_kind_returns_none(self, entry: FileEntry) -> None:
        classification = ClassificationResult(kind="binary")
        policy = ErrorPolicy()
        payload = policy.apply(entry, classification)
        assert payload is None