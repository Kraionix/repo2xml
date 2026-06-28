# tests/unit/services/policies/test_binary_policy.py
"""Unit tests for BinaryPolicy."""

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from repo2xml.config import BinaryHandlingConfig, BinaryMode
from repo2xml.contracts import IngestorLike
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
    def binary_entry(self) -> FileEntry:
        return FileEntry(
            abs_path=Path("/repo/data.bin"),
            rel_path="data.bin",
            name="data.bin",
            size=100,
            mtime_ns=0,
            is_symlink=False,
        )

    @pytest.fixture
    def ingestor(self) -> IngestorLike:
        ing = MagicMock(spec=IngestorLike)
        ing.sha256_file.return_value = "abc123"
        ing.iter_base64_chunks.return_value = ["YQ==", "Ig=="]
        return ing

    @pytest.fixture
    def classification(self) -> ClassificationResult:
        return ClassificationResult(kind="binary")

    def test_skip_mode_returns_skipped(self, binary_entry: FileEntry, ingestor: IngestorLike, classification: ClassificationResult) -> None:
        config = BinaryHandlingConfig(mode=BinaryMode.skip)
        policy = BinaryPolicy(config, ingestor)
        payload = policy.apply(binary_entry, classification)
        assert isinstance(payload, SkippedPayload)
        assert payload.code == SkipCode.binary_skip_mode

    def test_hash_mode_returns_hash(self, binary_entry: FileEntry, ingestor: IngestorLike, classification: ClassificationResult) -> None:
        config = BinaryHandlingConfig(mode=BinaryMode.hash)
        policy = BinaryPolicy(config, ingestor)
        payload = policy.apply(binary_entry, classification)
        assert isinstance(payload, BinaryHashPayload)
        assert payload.sha256_hex == "abc123"
        ingestor.sha256_file.assert_called_once_with(binary_entry.abs_path)

    def test_hash_mode_size_limit(self, binary_entry: FileEntry, ingestor: IngestorLike, classification: ClassificationResult) -> None:
        config = BinaryHandlingConfig(mode=BinaryMode.hash, max_hash_size=50)
        policy = BinaryPolicy(config, ingestor)
        payload = policy.apply(binary_entry, classification)
        assert isinstance(payload, SkippedPayload)
        assert payload.code == SkipCode.hash_size_limit
        ingestor.sha256_file.assert_not_called()

    def test_hash_mode_error(self, binary_entry: FileEntry, ingestor: IngestorLike, classification: ClassificationResult) -> None:
        ingestor.sha256_file.side_effect = OSError("Permission denied")
        config = BinaryHandlingConfig(mode=BinaryMode.hash)
        policy = BinaryPolicy(config, ingestor)
        payload = policy.apply(binary_entry, classification)
        assert isinstance(payload, ErrorPayload)
        assert payload.code == ErrorCode.binary_hash_error

    def test_base64_mode_returns_base64(self, binary_entry: FileEntry, ingestor: IngestorLike, classification: ClassificationResult) -> None:
        config = BinaryHandlingConfig(mode=BinaryMode.base64)
        policy = BinaryPolicy(config, ingestor)
        payload = policy.apply(binary_entry, classification)
        assert isinstance(payload, BinaryBase64Payload)
        assert list(payload.chunks) == ["YQ==", "Ig=="]
        ingestor.iter_base64_chunks.assert_called_once_with(binary_entry.abs_path)

    def test_base64_mode_size_limit(self, binary_entry: FileEntry, ingestor: IngestorLike, classification: ClassificationResult) -> None:
        config = BinaryHandlingConfig(mode=BinaryMode.base64, max_base64_size=50)
        policy = BinaryPolicy(config, ingestor)
        payload = policy.apply(binary_entry, classification)
        assert isinstance(payload, SkippedPayload)
        assert payload.code == SkipCode.base64_size_limit
        ingestor.iter_base64_chunks.assert_not_called()

    def test_base64_mode_error(self, binary_entry: FileEntry, ingestor: IngestorLike, classification: ClassificationResult) -> None:
        ingestor.iter_base64_chunks.side_effect = OSError("IO error")
        config = BinaryHandlingConfig(mode=BinaryMode.base64)
        policy = BinaryPolicy(config, ingestor)
        payload = policy.apply(binary_entry, classification)
        assert isinstance(payload, ErrorPayload)
        assert payload.code == ErrorCode.base64_error

    def test_text_classification_returns_none(self, binary_entry: FileEntry, ingestor: IngestorLike) -> None:
        classification = ClassificationResult(kind="text", encoding="utf-8")
        config = BinaryHandlingConfig(mode=BinaryMode.hash)
        policy = BinaryPolicy(config, ingestor)
        payload = policy.apply(binary_entry, classification)
        assert payload is None