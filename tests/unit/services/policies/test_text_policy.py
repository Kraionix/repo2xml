# tests/unit/services/policies/test_text_policy.py
"""Unit tests for TextPolicy."""

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from repo2xml.config import TextHandlingConfig
from repo2xml.contracts import IngestorLike
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
    def text_entry(self) -> FileEntry:
        return FileEntry(
            abs_path=Path("/repo/file.txt"),
            rel_path="file.txt",
            name="file.txt",
            size=100,
            mtime_ns=0,
            is_symlink=False,
        )

    @pytest.fixture
    def ingestor(self) -> IngestorLike:
        ing = MagicMock(spec=IngestorLike)
        read_result = MagicMock()
        read_result.kind = "text"
        read_result.text = "hello world"
        read_result.encoding = "utf-8"
        ing.read_text.return_value = read_result
        return ing

    @pytest.fixture
    def classification(self) -> ClassificationResult:
        return ClassificationResult(kind="text", encoding="utf-8", sample=b"hello")

    def test_success(self, text_entry: FileEntry, ingestor: IngestorLike, classification: ClassificationResult) -> None:
        config = TextHandlingConfig(max_text_size=1000)
        policy = TextPolicy(config, ingestor)
        payload = policy.apply(text_entry, classification)
        assert isinstance(payload, TextPayload)
        assert payload.text == "hello world"
        assert payload.encoding == "utf-8"
        ingestor.read_text.assert_called_once_with(
            text_entry.abs_path,
            max_size=1000,
            sniff_sample=b"hello",
        )

    def test_size_limit(self, text_entry: FileEntry, ingestor: IngestorLike, classification: ClassificationResult) -> None:
        config = TextHandlingConfig(max_text_size=10)
        policy = TextPolicy(config, ingestor)
        payload = policy.apply(text_entry, classification)
        assert isinstance(payload, SkippedPayload)
        assert payload.code == SkipCode.text_size_limit
        ingestor.read_text.assert_not_called()

    def test_read_error(self, text_entry: FileEntry, ingestor: IngestorLike, classification: ClassificationResult) -> None:
        read_result = MagicMock()
        read_result.kind = "error"
        read_result.error = MagicMock(code=ErrorCode.text_read_error, detail={"os_error": "fail"})
        ingestor.read_text.return_value = read_result

        config = TextHandlingConfig(max_text_size=1000)
        policy = TextPolicy(config, ingestor)
        payload = policy.apply(text_entry, classification)
        assert isinstance(payload, ErrorPayload)
        assert payload.code == ErrorCode.text_read_error

    def test_read_skip(self, text_entry: FileEntry, ingestor: IngestorLike, classification: ClassificationResult) -> None:
        read_result = MagicMock()
        read_result.kind = "skip"
        read_result.skipped = MagicMock(code=SkipCode.unknown, detail={})
        ingestor.read_text.return_value = read_result

        config = TextHandlingConfig(max_text_size=1000)
        policy = TextPolicy(config, ingestor)
        payload = policy.apply(text_entry, classification)
        assert isinstance(payload, SkippedPayload)
        assert payload.code == SkipCode.unknown

    def test_binary_classification_returns_none(self, text_entry: FileEntry, ingestor: IngestorLike) -> None:
        classification = ClassificationResult(kind="binary")
        config = TextHandlingConfig(max_text_size=1000)
        policy = TextPolicy(config, ingestor)
        payload = policy.apply(text_entry, classification)
        assert payload is None