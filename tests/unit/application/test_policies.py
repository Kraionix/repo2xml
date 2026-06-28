# tests/unit/application/test_policies.py
"""Unit tests for ExportPayloadBuilder and policies."""

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from repo2xml.application.policies import (
    BinaryPolicy,
    ExportPayloadBuilder,
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


class TestSymlinkPolicy:
    @pytest.fixture
    def symlink_entry(self) -> FileEntry:
        return FileEntry(
            abs_path=Path("/repo/link"),
            rel_path="link",
            name="link",
            size=0,
            mtime_ns=0,
            is_symlink=True,
            symlink_target="/target",
        )

    def test_as_link(self, symlink_entry) -> None:
        policy = SymlinkPolicy(symlinks_files=SymlinkFilesMode.as_link)
        payload = policy.apply(symlink_entry)
        assert isinstance(payload, LinkPayload)
        assert payload.link_target == "/target"

    def test_skip(self, symlink_entry) -> None:
        policy = SymlinkPolicy(symlinks_files=SymlinkFilesMode.skip)
        payload = policy.apply(symlink_entry)
        assert isinstance(payload, SkippedPayload)
        assert payload.code == SkipCode.unknown

    def test_follow_returns_none(self, symlink_entry) -> None:
        policy = SymlinkPolicy(symlinks_files=SymlinkFilesMode.follow)
        payload = policy.apply(symlink_entry)
        assert payload is None

    def test_regular_file_returns_none(self) -> None:
        entry = FileEntry(
            abs_path=Path("/a"),
            rel_path="a",
            name="a",
            size=0,
            mtime_ns=0,
            is_symlink=False,
        )
        policy = SymlinkPolicy(symlinks_files=SymlinkFilesMode.as_link)
        payload = policy.apply(entry)
        assert payload is None


class TestModePolicy:
    def test_metadata_mode(self) -> None:
        policy = ModePolicy(mode=Mode.metadata)
        entry = FileEntry(abs_path=Path("/a"), rel_path="a", name="a", size=0, mtime_ns=0, is_symlink=False)
        payload = policy.apply(entry)
        assert isinstance(payload, MetadataPayload)

    def test_full_mode_returns_none(self) -> None:
        policy = ModePolicy(mode=Mode.full)
        entry = FileEntry(abs_path=Path("/a"), rel_path="a", name="a", size=0, mtime_ns=0, is_symlink=False)
        payload = policy.apply(entry)
        assert payload is None


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
    def ingestor(self) -> MagicMock:
        ing = MagicMock()
        ing.sha256_file.return_value = "abc123"
        ing.iter_base64_chunks.return_value = ["YQ==", "Ig=="]
        return ing

    def test_skip(self, binary_entry, ingestor) -> None:
        binary_cfg = BinaryHandlingConfig(mode=BinaryMode.skip)
        policy = BinaryPolicy(binary_cfg, ingestor)
        payload = policy.apply(binary_entry)
        assert isinstance(payload, SkippedPayload)
        assert payload.code == SkipCode.binary_skip_mode

    def test_hash(self, binary_entry, ingestor) -> None:
        binary_cfg = BinaryHandlingConfig(mode=BinaryMode.hash)
        policy = BinaryPolicy(binary_cfg, ingestor)
        payload = policy.apply(binary_entry)
        assert isinstance(payload, BinaryHashPayload)
        assert payload.sha256_hex == "abc123"
        ingestor.sha256_file.assert_called_once_with(binary_entry.abs_path)

    def test_hash_size_limit(self, binary_entry, ingestor) -> None:
        binary_cfg = BinaryHandlingConfig(mode=BinaryMode.hash, max_hash_size=50)
        policy = BinaryPolicy(binary_cfg, ingestor)
        payload = policy.apply(binary_entry)
        assert isinstance(payload, SkippedPayload)
        assert payload.code == SkipCode.hash_size_limit

    def test_hash_error(self, binary_entry, ingestor) -> None:
        ingestor.sha256_file.side_effect = OSError("Permission denied")
        binary_cfg = BinaryHandlingConfig(mode=BinaryMode.hash)
        policy = BinaryPolicy(binary_cfg, ingestor)
        payload = policy.apply(binary_entry)
        assert isinstance(payload, ErrorPayload)
        assert payload.code == ErrorCode.binary_hash_error

    def test_base64(self, binary_entry, ingestor) -> None:
        binary_cfg = BinaryHandlingConfig(mode=BinaryMode.base64)
        policy = BinaryPolicy(binary_cfg, ingestor)
        payload = policy.apply(binary_entry)
        assert isinstance(payload, BinaryBase64Payload)
        assert list(payload.chunks) == ["YQ==", "Ig=="]
        ingestor.iter_base64_chunks.assert_called_once_with(binary_entry.abs_path)

    def test_base64_size_limit(self, binary_entry, ingestor) -> None:
        binary_cfg = BinaryHandlingConfig(mode=BinaryMode.base64, max_base64_size=50)
        policy = BinaryPolicy(binary_cfg, ingestor)
        payload = policy.apply(binary_entry)
        assert isinstance(payload, SkippedPayload)
        assert payload.code == SkipCode.base64_size_limit

    def test_base64_error(self, binary_entry, ingestor) -> None:
        ingestor.iter_base64_chunks.side_effect = OSError("IO error")
        binary_cfg = BinaryHandlingConfig(mode=BinaryMode.base64)
        policy = BinaryPolicy(binary_cfg, ingestor)
        payload = policy.apply(binary_entry)
        assert isinstance(payload, ErrorPayload)
        assert payload.code == ErrorCode.base64_error


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
    def ingestor(self) -> MagicMock:
        ing = MagicMock()
        ing.read_text.return_value = MagicMock(
            kind="text",
            text="hello world",
            encoding="utf-8"
        )
        return ing

    @pytest.fixture
    def classification(self) -> ClassificationResult:
        return ClassificationResult(kind="text", encoding="utf-8", sample=b"hello")

    def test_success(self, text_entry, ingestor, classification) -> None:
        text_cfg = TextHandlingConfig(max_text_size=1000)
        policy = TextPolicy(text_cfg, ingestor)
        payload = policy.apply(text_entry, classification)
        assert isinstance(payload, TextPayload)
        assert payload.text == "hello world"
        assert payload.encoding == "utf-8"
        ingestor.read_text.assert_called_once_with(
            text_entry.abs_path,
            max_size=1000,
            sniff_sample=b"hello"
        )

    def test_size_limit(self, text_entry, ingestor, classification) -> None:
        text_cfg = TextHandlingConfig(max_text_size=10)
        policy = TextPolicy(text_cfg, ingestor)
        payload = policy.apply(text_entry, classification)
        assert isinstance(payload, SkippedPayload)
        assert payload.code == SkipCode.text_size_limit

    def test_read_error(self, text_entry, ingestor, classification) -> None:
        ingestor.read_text.return_value = MagicMock(
            kind="error",
            error=MagicMock(code=ErrorCode.text_read_error, detail={})
        )
        text_cfg = TextHandlingConfig(max_text_size=1000)
        policy = TextPolicy(text_cfg, ingestor)
        payload = policy.apply(text_entry, classification)
        assert isinstance(payload, ErrorPayload)
        assert payload.code == ErrorCode.text_read_error

    def test_read_skip(self, text_entry, ingestor, classification) -> None:
        ingestor.read_text.return_value = MagicMock(
            kind="skip",
            skipped=MagicMock(code=SkipCode.text_size_limit, detail={})
        )
        text_cfg = TextHandlingConfig(max_text_size=1000)
        policy = TextPolicy(text_cfg, ingestor)
        payload = policy.apply(text_entry, classification)
        assert isinstance(payload, SkippedPayload)
        assert payload.code == SkipCode.text_size_limit


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

    @pytest.fixture
    def ingestor(self) -> MagicMock:
        ing = MagicMock()
        ing.read_text.return_value = MagicMock(kind="text", text="content", encoding="utf-8")
        return ing

    def test_build_text(self, entry, ingestor) -> None:
        builder = ExportPayloadBuilder(
            mode=Mode.full,
            binary=BinaryHandlingConfig(mode=BinaryMode.skip),
            text=TextHandlingConfig(max_text_size=1000),
            symlinks_files=SymlinkFilesMode.follow,
            ingestor=ingestor,
        )
        classification = ClassificationResult(kind="text", encoding="utf-8")
        payload = builder.build(entry, classification)
        assert isinstance(payload, TextPayload)
        assert payload.text == "content"

    def test_build_binary_skip(self, entry, ingestor) -> None:
        builder = ExportPayloadBuilder(
            mode=Mode.full,
            binary=BinaryHandlingConfig(mode=BinaryMode.skip),
            text=TextHandlingConfig(),
            symlinks_files=SymlinkFilesMode.follow,
            ingestor=ingestor,
        )
        classification = ClassificationResult(kind="binary")
        payload = builder.build(entry, classification)
        assert isinstance(payload, SkippedPayload)
        assert payload.code == SkipCode.binary_skip_mode

    def test_build_metadata_mode(self, entry, ingestor) -> None:
        builder = ExportPayloadBuilder(
            mode=Mode.metadata,
            binary=BinaryHandlingConfig(),
            text=TextHandlingConfig(),
            symlinks_files=SymlinkFilesMode.follow,
            ingestor=ingestor,
        )
        classification = ClassificationResult(kind="text")
        payload = builder.build(entry, classification)
        assert isinstance(payload, MetadataPayload)

    def test_build_symlink_as_link(self, entry, ingestor) -> None:
        sym_entry = FileEntry(
            abs_path=Path("/repo/link"),
            rel_path="link",
            name="link",
            size=0,
            mtime_ns=0,
            is_symlink=True,
            symlink_target="/target",
        )
        builder = ExportPayloadBuilder(
            mode=Mode.full,
            binary=BinaryHandlingConfig(),
            text=TextHandlingConfig(),
            symlinks_files=SymlinkFilesMode.as_link,
            ingestor=ingestor,
        )
        classification = ClassificationResult(kind="text")
        payload = builder.build(sym_entry, classification)
        assert isinstance(payload, LinkPayload)

    def test_build_classification_error(self, entry, ingestor) -> None:
        builder = ExportPayloadBuilder(
            mode=Mode.full,
            binary=BinaryHandlingConfig(),
            text=TextHandlingConfig(),
            symlinks_files=SymlinkFilesMode.follow,
            ingestor=ingestor,
        )
        classification = ClassificationResult(kind="error", error="read failed")
        payload = builder.build(entry, classification)
        assert isinstance(payload, ErrorPayload)
        assert payload.code == ErrorCode.sniff_read_error

    def test_build_binary_hash(self, entry, ingestor) -> None:
        builder = ExportPayloadBuilder(
            mode=Mode.full,
            binary=BinaryHandlingConfig(mode=BinaryMode.hash),
            text=TextHandlingConfig(),
            symlinks_files=SymlinkFilesMode.follow,
            ingestor=ingestor,
        )
        classification = ClassificationResult(kind="binary")
        payload = builder.build(entry, classification)
        assert isinstance(payload, BinaryHashPayload)