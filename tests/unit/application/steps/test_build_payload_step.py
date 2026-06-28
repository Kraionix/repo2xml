# tests/unit/application/steps/test_build_payload_step.py
"""Unit tests for BuildPayloadStep with the new policy chain."""

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from repo2xml.application.steps.build_payload_step import BuildPayloadStep
from repo2xml.contracts import FilePolicy
from repo2xml.domain.model import (
    BinaryBase64Payload,
    BinaryHashPayload,
    ClassificationResult,
    ErrorCode,
    ErrorPayload,
    FileEntry,
    LinkPayload,
    MetadataPayload,
    SkipCode,
    SkippedPayload,
    TextPayload,
    ProcessingInput,
    ProcessingResult,
)
from repo2xml.services.policies import (
    BinaryPolicy,
    ErrorPolicy,
    ModePolicy,
    SymlinkPolicy,
    TextPolicy,
)
from repo2xml.config import (
    BinaryHandlingConfig,
    BinaryMode,
    Mode,
    SymlinkFilesMode,
    TextHandlingConfig,
)


class TestBuildPayloadStep:
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
        read_result.text = "content"
        read_result.encoding = "utf-8"
        ing.read_text.return_value = read_result
        ing.sha256_file.return_value = "abc123"
        ing.iter_base64_chunks.return_value = ["YQ==", "Ig=="]
        return ing

    def test_symlink_as_link(self, entry: FileEntry) -> None:
        entry.is_symlink = True
        entry.symlink_target = "/target"
        policies: list[FilePolicy] = [
            SymlinkPolicy(SymlinkFilesMode.as_link),
            ErrorPolicy(),
            BinaryPolicy(BinaryHandlingConfig(mode=BinaryMode.skip), MagicMock()),
            TextPolicy(TextHandlingConfig(max_text_size=1000), MagicMock()),
        ]
        step = BuildPayloadStep(policies, mode=Mode.full)
        classification = ClassificationResult(kind="text")
        input = ProcessingInput(entry=entry)
        result = ProcessingResult()
        result.classification = classification
        step.process(input, result)

        assert isinstance(result.payload, LinkPayload)
        assert result.payload.link_target == "/target"
        assert result.is_success is True
        assert result.should_stop is False

    def test_symlink_skip(self, entry: FileEntry) -> None:
        entry.is_symlink = True
        policies: list[FilePolicy] = [
            SymlinkPolicy(SymlinkFilesMode.skip),
            ErrorPolicy(),
            BinaryPolicy(BinaryHandlingConfig(mode=BinaryMode.skip), MagicMock()),
            TextPolicy(TextHandlingConfig(max_text_size=1000), MagicMock()),
        ]
        step = BuildPayloadStep(policies, mode=Mode.full)
        classification = ClassificationResult(kind="text")
        input = ProcessingInput(entry=entry)
        result = ProcessingResult()
        result.classification = classification
        step.process(input, result)

        assert isinstance(result.payload, SkippedPayload)
        assert result.payload.code == SkipCode.unknown
        assert result.is_success is False
        assert result.should_stop is True
        assert result.skip_code == SkipCode.unknown

    def test_metadata_mode(self, entry: FileEntry) -> None:
        policies: list[FilePolicy] = [ModePolicy(Mode.metadata)]
        step = BuildPayloadStep(policies, mode=Mode.metadata)
        classification = ClassificationResult(kind="text")
        input = ProcessingInput(entry=entry)
        result = ProcessingResult()
        result.classification = classification
        step.process(input, result)

        assert isinstance(result.payload, MetadataPayload)
        assert result.is_success is True
        assert result.should_stop is False

    def test_classification_error(self, entry: FileEntry) -> None:
        policies: list[FilePolicy] = [
            ErrorPolicy(),
            BinaryPolicy(BinaryHandlingConfig(mode=BinaryMode.skip), MagicMock()),
            TextPolicy(TextHandlingConfig(max_text_size=1000), MagicMock()),
        ]
        step = BuildPayloadStep(policies, mode=Mode.full)
        classification = ClassificationResult(kind="error", error="failed")
        input = ProcessingInput(entry=entry)
        result = ProcessingResult()
        result.classification = classification
        step.process(input, result)

        assert isinstance(result.payload, ErrorPayload)
        assert result.payload.code == ErrorCode.sniff_read_error
        assert result.is_success is False
        assert result.should_stop is True
        assert result.error_code == ErrorCode.sniff_read_error

    def test_binary_skip(self, entry: FileEntry, ingestor: MagicMock) -> None:
        policies: list[FilePolicy] = [
            ErrorPolicy(),
            BinaryPolicy(BinaryHandlingConfig(mode=BinaryMode.skip), ingestor),
            TextPolicy(TextHandlingConfig(max_text_size=1000), ingestor),
        ]
        step = BuildPayloadStep(policies, mode=Mode.full)
        classification = ClassificationResult(kind="binary")
        input = ProcessingInput(entry=entry)
        result = ProcessingResult()
        result.classification = classification
        step.process(input, result)

        assert isinstance(result.payload, SkippedPayload)
        assert result.payload.code == SkipCode.binary_skip_mode
        assert result.is_success is False
        assert result.should_stop is True

    def test_binary_hash(self, entry: FileEntry, ingestor: MagicMock) -> None:
        policies: list[FilePolicy] = [
            ErrorPolicy(),
            BinaryPolicy(BinaryHandlingConfig(mode=BinaryMode.hash), ingestor),
            TextPolicy(TextHandlingConfig(max_text_size=1000), ingestor),
        ]
        step = BuildPayloadStep(policies, mode=Mode.full)
        classification = ClassificationResult(kind="binary")
        input = ProcessingInput(entry=entry)
        result = ProcessingResult()
        result.classification = classification
        step.process(input, result)

        assert isinstance(result.payload, BinaryHashPayload)
        assert result.payload.sha256_hex == "abc123"
        assert result.is_success is True
        assert result.should_stop is False

    def test_binary_base64(self, entry: FileEntry, ingestor: MagicMock) -> None:
        policies: list[FilePolicy] = [
            ErrorPolicy(),
            BinaryPolicy(BinaryHandlingConfig(mode=BinaryMode.base64), ingestor),
            TextPolicy(TextHandlingConfig(max_text_size=1000), ingestor),
        ]
        step = BuildPayloadStep(policies, mode=Mode.full)
        classification = ClassificationResult(kind="binary")
        input = ProcessingInput(entry=entry)
        result = ProcessingResult()
        result.classification = classification
        step.process(input, result)

        assert isinstance(result.payload, BinaryBase64Payload)
        assert list(result.payload.chunks) == ["YQ==", "Ig=="]
        assert result.is_success is True
        assert result.should_stop is False

    def test_text_success(self, entry: FileEntry, ingestor: MagicMock) -> None:
        policies: list[FilePolicy] = [
            ErrorPolicy(),
            BinaryPolicy(BinaryHandlingConfig(mode=BinaryMode.skip), ingestor),
            TextPolicy(TextHandlingConfig(max_text_size=1000), ingestor),
        ]
        step = BuildPayloadStep(policies, mode=Mode.full)
        classification = ClassificationResult(kind="text", encoding="utf-8", sample=b"sample")
        input = ProcessingInput(entry=entry)
        result = ProcessingResult()
        result.classification = classification
        step.process(input, result)

        assert isinstance(result.payload, TextPayload)
        assert result.payload.text == "content"
        assert result.payload.encoding == "utf-8"
        assert result.is_success is True
        assert result.should_stop is False
        ingestor.read_text.assert_called_once_with(
            entry.abs_path,
            max_size=1000,
            sniff_sample=b"sample",
        )

    def test_text_size_limit(self, entry: FileEntry, ingestor: MagicMock) -> None:
        policies: list[FilePolicy] = [
            ErrorPolicy(),
            BinaryPolicy(BinaryHandlingConfig(mode=BinaryMode.skip), ingestor),
            TextPolicy(TextHandlingConfig(max_text_size=10), ingestor),
        ]
        step = BuildPayloadStep(policies, mode=Mode.full)
        classification = ClassificationResult(kind="text")
        input = ProcessingInput(entry=entry)
        result = ProcessingResult()
        result.classification = classification
        step.process(input, result)

        assert isinstance(result.payload, SkippedPayload)
        assert result.payload.code == SkipCode.text_size_limit
        assert result.is_success is False
        assert result.should_stop is True
        ingestor.read_text.assert_not_called()

    def test_text_read_error(self, entry: FileEntry, ingestor: MagicMock) -> None:
        read_result = MagicMock()
        read_result.kind = "error"
        read_result.error = MagicMock(code=ErrorCode.text_read_error, detail={})
        ingestor.read_text.return_value = read_result

        policies: list[FilePolicy] = [
            ErrorPolicy(),
            BinaryPolicy(BinaryHandlingConfig(mode=BinaryMode.skip), ingestor),
            TextPolicy(TextHandlingConfig(max_text_size=1000), ingestor),
        ]
        step = BuildPayloadStep(policies, mode=Mode.full)
        classification = ClassificationResult(kind="text")
        input = ProcessingInput(entry=entry)
        result = ProcessingResult()
        result.classification = classification
        step.process(input, result)

        assert isinstance(result.payload, ErrorPayload)
        assert result.payload.code == ErrorCode.text_read_error
        assert result.is_success is False
        assert result.should_stop is True

    def test_missing_classification_in_full_mode(self, entry: FileEntry) -> None:
        policies: list[FilePolicy] = [
            ErrorPolicy(),
        ]
        step = BuildPayloadStep(policies, mode=Mode.full)
        input = ProcessingInput(entry=entry)
        result = ProcessingResult()
        # Do NOT set result.classification
        step.process(input, result)

        assert result.should_stop is True
        assert result.is_success is False
        assert result.error_code == ErrorCode.unknown
        assert result.message == "Classification result is missing"

    def test_missing_classification_in_metadata_mode(self, entry: FileEntry) -> None:
        policies: list[FilePolicy] = [ModePolicy(Mode.metadata)]
        step = BuildPayloadStep(policies, mode=Mode.metadata)
        input = ProcessingInput(entry=entry)
        result = ProcessingResult()
        # No classification set – should be fine in metadata mode
        step.process(input, result)

        assert isinstance(result.payload, MetadataPayload)
        assert result.is_success is True
        assert result.should_stop is False