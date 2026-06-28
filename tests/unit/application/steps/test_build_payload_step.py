# tests/unit/application/steps/test_build_payload_step.py
"""Unit tests for BuildPayloadStep."""

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from repo2xml.application.processing_context import ProcessingContext
from repo2xml.application.steps.build_payload_step import BuildPayloadStep
from repo2xml.config import BinaryHandlingConfig, BinaryMode, Mode, SymlinkFilesMode, TextHandlingConfig
from repo2xml.contracts import IngestorLike
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


class TestBuildPayloadStep:
    @pytest.fixture
    def ingestor(self) -> MagicMock:
        ing = MagicMock(spec=IngestorLike)
        read_result = MagicMock()
        read_result.kind = "text"
        read_result.text = "content"
        read_result.encoding = "utf-8"
        ing.read_text.return_value = read_result
        ing.sha256_file.return_value = "abc123"
        ing.iter_base64_chunks.return_value = ["YQ==", "Ig=="]
        return ing

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

    def test_symlink_as_link(self, entry: FileEntry) -> None:
        entry.is_symlink = True
        entry.symlink_target = "/target"
        config_binary = BinaryHandlingConfig(mode=BinaryMode.skip)
        config_text = TextHandlingConfig(max_text_size=1000)
        step = BuildPayloadStep(
            ingestor=MagicMock(),
            mode=Mode.full,
            binary=config_binary,
            text=config_text,
            symlinks_files=SymlinkFilesMode.as_link,
        )
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
        step = BuildPayloadStep(
            ingestor=MagicMock(),
            mode=Mode.full,
            binary=BinaryHandlingConfig(mode=BinaryMode.skip),
            text=TextHandlingConfig(max_text_size=1000),
            symlinks_files=SymlinkFilesMode.skip,
        )
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
        step = BuildPayloadStep(
            ingestor=MagicMock(),
            mode=Mode.metadata,
            binary=BinaryHandlingConfig(mode=BinaryMode.skip),
            text=TextHandlingConfig(max_text_size=1000),
            symlinks_files=SymlinkFilesMode.follow,
        )
        classification = ClassificationResult(kind="text")
        ctx = ProcessingContext(entry=entry)
        ctx.classification = classification
        step.process(ctx)

        assert isinstance(ctx.payload, MetadataPayload)
        assert ctx.is_success is True
        assert ctx.should_stop is False

    def test_classification_error(self, entry: FileEntry) -> None:
        step = BuildPayloadStep(
            ingestor=MagicMock(),
            mode=Mode.full,
            binary=BinaryHandlingConfig(mode=BinaryMode.skip),
            text=TextHandlingConfig(max_text_size=1000),
            symlinks_files=SymlinkFilesMode.follow,
        )
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
        step = BuildPayloadStep(
            ingestor=ingestor,
            mode=Mode.full,
            binary=BinaryHandlingConfig(mode=BinaryMode.skip),
            text=TextHandlingConfig(max_text_size=1000),
            symlinks_files=SymlinkFilesMode.follow,
        )
        classification = ClassificationResult(kind="binary")
        ctx = ProcessingContext(entry=entry)
        ctx.classification = classification
        step.process(ctx)

        assert isinstance(ctx.payload, SkippedPayload)
        assert ctx.payload.code == SkipCode.binary_skip_mode
        assert ctx.is_success is False
        assert ctx.should_stop is True

    def test_binary_hash(self, entry: FileEntry, ingestor: MagicMock) -> None:
        step = BuildPayloadStep(
            ingestor=ingestor,
            mode=Mode.full,
            binary=BinaryHandlingConfig(mode=BinaryMode.hash),
            text=TextHandlingConfig(max_text_size=1000),
            symlinks_files=SymlinkFilesMode.follow,
        )
        classification = ClassificationResult(kind="binary")
        ctx = ProcessingContext(entry=entry)
        ctx.classification = classification
        step.process(ctx)

        assert isinstance(ctx.payload, BinaryHashPayload)
        assert ctx.payload.sha256_hex == "abc123"
        assert ctx.is_success is True
        assert ctx.should_stop is False

    def test_binary_base64(self, entry: FileEntry, ingestor: MagicMock) -> None:
        step = BuildPayloadStep(
            ingestor=ingestor,
            mode=Mode.full,
            binary=BinaryHandlingConfig(mode=BinaryMode.base64),
            text=TextHandlingConfig(max_text_size=1000),
            symlinks_files=SymlinkFilesMode.follow,
        )
        classification = ClassificationResult(kind="binary")
        ctx = ProcessingContext(entry=entry)
        ctx.classification = classification
        step.process(ctx)

        assert isinstance(ctx.payload, BinaryBase64Payload)
        assert list(ctx.payload.chunks) == ["YQ==", "Ig=="]
        assert ctx.is_success is True
        assert ctx.should_stop is False

    def test_text_success(self, entry: FileEntry, ingestor: MagicMock) -> None:
        step = BuildPayloadStep(
            ingestor=ingestor,
            mode=Mode.full,
            binary=BinaryHandlingConfig(mode=BinaryMode.skip),
            text=TextHandlingConfig(max_text_size=1000),
            symlinks_files=SymlinkFilesMode.follow,
        )
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
        step = BuildPayloadStep(
            ingestor=ingestor,
            mode=Mode.full,
            binary=BinaryHandlingConfig(mode=BinaryMode.skip),
            text=TextHandlingConfig(max_text_size=10),  # smaller than file size
            symlinks_files=SymlinkFilesMode.follow,
        )
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

        step = BuildPayloadStep(
            ingestor=ingestor,
            mode=Mode.full,
            binary=BinaryHandlingConfig(mode=BinaryMode.skip),
            text=TextHandlingConfig(max_text_size=1000),
            symlinks_files=SymlinkFilesMode.follow,
        )
        classification = ClassificationResult(kind="text")
        ctx = ProcessingContext(entry=entry)
        ctx.classification = classification
        step.process(ctx)

        assert isinstance(ctx.payload, ErrorPayload)
        assert ctx.payload.code == ErrorCode.text_read_error
        assert ctx.is_success is False
        assert ctx.should_stop is True