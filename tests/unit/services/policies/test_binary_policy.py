# tests/unit/services/policies/test_binary_policy.py
"""Unit tests for BinaryPolicy."""

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from repo2xml.config import BinaryHandlingConfig, BinaryMode
from repo2xml.domain.model import (
    BinaryBase64Payload,
    BinaryHashPayload,
    ClassificationResult,
    ErrorCode,
    ErrorPayload,
    FileEntry,
    SkipCode,
    SkippedPayload,
)
from repo2xml.services.policies import BinaryPolicy


class TestBinaryPolicy:
    @pytest.fixture
    def entry(self) -> FileEntry:
        return FileEntry(
            abs_path=Path("/repo/data.bin"),
            rel_path="data.bin",
            name="data.bin",
            size=100,
            mtime_ns=0,
            is_symlink=False,
        )

    @pytest.fixture
    def classification(self) -> ClassificationResult:
        return ClassificationResult(kind="binary")

    @pytest.fixture
    def ingestor(self) -> MagicMock:
        ing = MagicMock()
        ing.sha256_file.return_value = "abc123"
        ing.iter_base64_chunks.return_value = ["YQ==", "Ig=="]
        return ing

    def test_binary_skip(self, entry: FileEntry, classification: ClassificationResult, ingestor: MagicMock) -> None:
        policy = BinaryPolicy(BinaryHandlingConfig(mode=BinaryMode.skip), ingestor)
        result = policy.apply(entry, classification)
        assert isinstance(result, SkippedPayload)
        assert result.code == SkipCode.binary_skip_mode

    def test_binary_hash(self, entry: FileEntry, classification: ClassificationResult, ingestor: MagicMock) -> None:
        policy = BinaryPolicy(BinaryHandlingConfig(mode=BinaryMode.hash), ingestor)
        result = policy.apply(entry, classification)
        assert isinstance(result, BinaryHashPayload)
        assert result.sha256_hex == "abc123"
        ingestor.sha256_file.assert_called_once_with(entry.abs_path)

    def test_binary_hash_exceeds_limit(self, entry: FileEntry, classification: ClassificationResult, ingestor: MagicMock) -> None:
        policy = BinaryPolicy(
            BinaryHandlingConfig(mode=BinaryMode.hash, max_hash_size=50),  # smaller than file size 100
            ingestor,
        )
        result = policy.apply(entry, classification)
        assert isinstance(result, SkippedPayload)
        assert result.code == SkipCode.hash_size_limit
        ingestor.sha256_file.assert_not_called()

    def test_binary_hash_os_error(self, entry: FileEntry, classification: ClassificationResult, ingestor: MagicMock) -> None:
        ingestor.sha256_file.side_effect = OSError("permission denied")
        policy = BinaryPolicy(BinaryHandlingConfig(mode=BinaryMode.hash), ingestor)
        result = policy.apply(entry, classification)
        assert isinstance(result, ErrorPayload)
        assert result.code == ErrorCode.binary_hash_error
        assert "permission denied" in result.message

    def test_binary_base64(self, entry: FileEntry, classification: ClassificationResult, ingestor: MagicMock) -> None:
        policy = BinaryPolicy(BinaryHandlingConfig(mode=BinaryMode.base64), ingestor)
        result = policy.apply(entry, classification)
        assert isinstance(result, BinaryBase64Payload)
        assert list(result.chunks) == ["YQ==", "Ig=="]
        ingestor.iter_base64_chunks.assert_called_once_with(entry.abs_path)

    def test_binary_base64_exceeds_limit(self, entry: FileEntry, classification: ClassificationResult, ingestor: MagicMock) -> None:
        policy = BinaryPolicy(
            BinaryHandlingConfig(mode=BinaryMode.base64, max_base64_size=50),
            ingestor,
        )
        result = policy.apply(entry, classification)
        assert isinstance(result, SkippedPayload)
        assert result.code == SkipCode.base64_size_limit
        ingestor.iter_base64_chunks.assert_not_called()

    def test_binary_base64_os_error(self, entry: FileEntry, classification: ClassificationResult, ingestor: MagicMock) -> None:
        ingestor.iter_base64_chunks.side_effect = OSError("io error")
        policy = BinaryPolicy(BinaryHandlingConfig(mode=BinaryMode.base64), ingestor)
        result = policy.apply(entry, classification)
        assert isinstance(result, ErrorPayload)
        assert result.code == ErrorCode.base64_error
        assert "io error" in result.message

    def test_non_binary_returns_none(self, entry: FileEntry, ingestor: MagicMock) -> None:
        classification = ClassificationResult(kind="text")
        policy = BinaryPolicy(BinaryHandlingConfig(mode=BinaryMode.skip), ingestor)
        result = policy.apply(entry, classification)
        assert result is None