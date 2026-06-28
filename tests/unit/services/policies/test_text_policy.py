# tests/unit/services/policies/test_text_policy.py
"""Unit tests for TextPolicy."""

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from repo2xml.config import TextHandlingConfig
from repo2xml.domain.model import (
    ClassificationResult,
    ErrorCode,
    ErrorPayload,
    FileEntry,
    SkipCode,
    SkippedPayload,
    TextPayload,
)
from repo2xml.services.policies import TextPolicy


class TestTextPolicy:
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

    @pytest.fixture
    def ingestor(self) -> MagicMock:
        ing = MagicMock()
        read_result = MagicMock()
        read_result.kind = "text"
        read_result.text = "hello world"
        read_result.encoding = "utf-8"
        ing.read_text.return_value = read_result
        return ing

    def test_text_success(self, entry: FileEntry, ingestor: MagicMock) -> None:
        classification = ClassificationResult(kind="text", encoding="utf-8", sample=b"sample")
        policy = TextPolicy(TextHandlingConfig(max_text_size=1000), ingestor)
        result = policy.apply(entry, classification)
        assert isinstance(result, TextPayload)
        assert result.text == "hello world"
        assert result.encoding == "utf-8"
        ingestor.read_text.assert_called_once_with(
            entry.abs_path,
            max_size=1000,
            sniff_sample=b"sample",
        )

    def test_text_exceeds_limit(self, entry: FileEntry, ingestor: MagicMock) -> None:
        classification = ClassificationResult(kind="text")
        policy = TextPolicy(TextHandlingConfig(max_text_size=10), ingestor)  # smaller than file size 100
        result = policy.apply(entry, classification)
        assert isinstance(result, SkippedPayload)
        assert result.code == SkipCode.text_size_limit
        ingestor.read_text.assert_not_called()

    def test_text_read_error(self, entry: FileEntry, ingestor: MagicMock) -> None:
        read_result = MagicMock()
        read_result.kind = "error"
        read_result.error = MagicMock(code=ErrorCode.text_read_error, detail={})
        ingestor.read_text.return_value = read_result

        classification = ClassificationResult(kind="text")
        policy = TextPolicy(TextHandlingConfig(max_text_size=1000), ingestor)
        result = policy.apply(entry, classification)
        assert isinstance(result, ErrorPayload)
        assert result.code == ErrorCode.text_read_error

    def test_text_skip_from_ingestor(self, entry: FileEntry, ingestor: MagicMock) -> None:
        read_result = MagicMock()
        read_result.kind = "skip"
        read_result.skipped = MagicMock(code=SkipCode.unknown)
        ingestor.read_text.return_value = read_result

        classification = ClassificationResult(kind="text")
        policy = TextPolicy(TextHandlingConfig(max_text_size=1000), ingestor)
        result = policy.apply(entry, classification)
        assert isinstance(result, SkippedPayload)
        assert result.code == SkipCode.unknown

    def test_non_text_returns_none(self, entry: FileEntry, ingestor: MagicMock) -> None:
        classification = ClassificationResult(kind="binary")
        policy = TextPolicy(TextHandlingConfig(max_text_size=1000), ingestor)
        result = policy.apply(entry, classification)
        assert result is None