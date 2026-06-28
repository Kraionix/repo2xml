# tests/unit/application/steps/test_build_payload_step.py
"""Unit tests for BuildPayloadStep with the new policy chain."""

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from repo2xml.application.processing_context import ProcessingContext
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
        step = BuildPayloadStep(policies)
        classification = ClassificationResult(kind="text")
        ctx = ProcessingContext(entry=entry)
        ctx.classification = classification
        step.process(ctx)

        assert isinstance(ctx.payload, LinkPayload)
        assert ctx.payload.link_target == "/target"
        assert ctx.is_success is True
        assert ctx.should_stop is False

    def test_symlink_skip(self, entry: FileEntry) -> None:
        entry.is_symlink = True
        policies: list[FilePolicy] = [
            SymlinkPolicy(SymlinkFilesMode.skip),
            ErrorPolicy(),
            BinaryPolicy(BinaryHandlingConfig(mode=BinaryMode.skip), MagicMock()),
            TextPolicy(TextHandlingConfig(max_text_size=1000), MagicMock()),
        ]
        step = BuildPayloadStep(policies)
        classification = ClassificationResult(kind="text")
        ctx = ProcessingContext(entry=entry)
        ctx.classification = classification
        step.process(ctx)

        assert isinstance(ctx.payload, SkippedPayload)
        assert ctx.payload.code == SkipCode.unknown
        assert ctx.is_success is False
        assert ctx.should_stop is True
        assert ctx.skip_code == SkipCode.unknown.value

    def test_metadata_mode(self, entry: FileEntry) -> None:
        # In metadata mode, only ModePolicy is present in the chain.
        policies: list[FilePolicy] = [ModePolicy(Mode.metadata)]
        step = BuildPayloadStep(policies)
        classification = ClassificationResult(kind="text")
        ctx = ProcessingContext(entry=entry)
        ctx.classification = classification
        step.process(ctx)

        assert isinstance(ctx.payload, MetadataPayload)
        assert ctx.is_success is True
        assert ctx.should_stop is False

    def test_classification_error(self, entry: FileEntry) -> None:
        policies: list[FilePolicy] = [
            ErrorPolicy(),
            BinaryPolicy(BinaryHandlingConfig(mode=BinaryMode.skip), MagicMock()),
            TextPolicy(TextHandlingConfig(max_text_size=1000), MagicMock()),
        ]
        step = BuildPayloadStep(policies)
        classification = ClassificationResult(kind="error", error="failed")
        ctx = ProcessingContext(entry=entry)
        ctx.classification = classification
        step.process(ctx)

        assert isinstance(ctx.payload, ErrorPayload)
        assert ctx.payload.code == ErrorCode.sniff_read_error
        assert ctx.is_success is False
        assert ctx.should_stop is True
        assert ctx.error_code == ErrorCode.sniff_read_error.value

    def test_binary_skip(self, entry: FileEntry, ingestor: MagicMock) -> None:
        policies: list[FilePolicy] = [
            ErrorPolicy(),
            BinaryPolicy(BinaryHandlingConfig(mode=BinaryMode.skip), ingestor),
            TextPolicy(TextHandlingConfig(max_text_size=1000), ingestor),
        ]
        step = BuildPayloadStep(policies)
        classification = ClassificationResult(kind="binary")
        ctx = ProcessingContext(entry=entry)
        ctx.classification = classification
        step.process(ctx)

        assert isinstance(ctx.payload, SkippedPayload)
        assert ctx.payload.code == SkipCode.binary_skip_mode
        assert ctx.is_success is False
        assert ctx.should_stop is True

    def test_binary_hash(self, entry: FileEntry, ingestor: MagicMock) -> None:
        policies: list[FilePolicy] = [
            ErrorPolicy(),
            BinaryPolicy(BinaryHandlingConfig(mode=BinaryMode.hash), ingestor),
            TextPolicy(TextHandlingConfig(max_text_size=1000), ingestor),
        ]
        step = BuildPayloadStep(policies)
        classification = ClassificationResult(kind="binary")
        ctx = ProcessingContext(entry=entry)
        ctx.classification = classification
        step.process(ctx)

        assert isinstance(ctx.payload, BinaryHashPayload)
        assert ctx.payload.sha256_hex == "abc123"
        assert ctx.is_success is True
        assert ctx.should_stop is False

    def test_binary_base64(self, entry: FileEntry, ingestor: MagicMock) -> None:
        policies: list[FilePolicy] = [
            ErrorPolicy(),
            BinaryPolicy(BinaryHandlingConfig(mode=BinaryMode.base64), ingestor),
            TextPolicy(TextHandlingConfig(max_text_size=1000), ingestor),
        ]
        step = BuildPayloadStep(policies)
        classification = ClassificationResult(kind="binary")
        ctx = ProcessingContext(entry=entry)
        ctx.classification = classification
        step.process(ctx)

        assert isinstance(ctx.payload, BinaryBase64Payload)
        assert list(ctx.payload.chunks) == ["YQ==", "Ig=="]
        assert ctx.is_success is True
        assert ctx.should_stop is False

    def test_text_success(self, entry: FileEntry, ingestor: MagicMock) -> None:
        policies: list[FilePolicy] = [
            ErrorPolicy(),
            BinaryPolicy(BinaryHandlingConfig(mode=BinaryMode.skip), ingestor),
            TextPolicy(TextHandlingConfig(max_text_size=1000), ingestor),
        ]
        step = BuildPayloadStep(policies)
        classification = ClassificationResult(kind="text", encoding="utf-8", sample=b"sample")
        ctx = ProcessingContext(entry=entry)
        ctx.classification = classification
        step.process(ctx)

        assert isinstance(ctx.payload, TextPayload)
        assert ctx.payload.text == "content"
        assert ctx.payload.encoding == "utf-8"
        assert ctx.is_success is True
        assert ctx.should_stop is False
        ingestor.read_text.assert_called_once_with(
            entry.abs_path,
            max_size=1000,
            sniff_sample=b"sample",
        )

    def test_text_size_limit(self, entry: FileEntry, ingestor: MagicMock) -> None:
        policies: list[FilePolicy] = [
            ErrorPolicy(),
            BinaryPolicy(BinaryHandlingConfig(mode=BinaryMode.skip), ingestor),
            TextPolicy(TextHandlingConfig(max_text_size=10), ingestor),  # limit smaller than file size
        ]
        step = BuildPayloadStep(policies)
        classification = ClassificationResult(kind="text")
        ctx = ProcessingContext(entry=entry)
        ctx.classification = classification
        step.process(ctx)

        assert isinstance(ctx.payload, SkippedPayload)
        assert ctx.payload.code == SkipCode.text_size_limit
        assert ctx.is_success is False
        assert ctx.should_stop is True
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
        step = BuildPayloadStep(policies)
        classification = ClassificationResult(kind="text")
        ctx = ProcessingContext(entry=entry)
        ctx.classification = classification
        step.process(ctx)

        assert isinstance(ctx.payload, ErrorPayload)
        assert ctx.payload.code == ErrorCode.text_read_error
        assert ctx.is_success is False
        assert ctx.should_stop is True