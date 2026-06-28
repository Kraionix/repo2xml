# tests/unit/services/policies/test_symlink_policy.py
"""Unit tests for SymlinkPolicy."""

from pathlib import Path

import pytest

from repo2xml.config import SymlinkFilesMode
from repo2xml.domain.model import ClassificationResult, FileEntry, LinkPayload, SkipCode, SkippedPayload
from repo2xml.services.policies import SymlinkPolicy


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

    @pytest.fixture
    def regular_entry(self) -> FileEntry:
        return FileEntry(
            abs_path=Path("/repo/file.txt"),
            rel_path="file.txt",
            name="file.txt",
            size=100,
            mtime_ns=0,
            is_symlink=False,
        )

    @pytest.fixture
    def classification(self) -> ClassificationResult:
        return ClassificationResult(kind="text", encoding="utf-8")

    def test_as_link_returns_link_payload(self, symlink_entry: FileEntry, classification: ClassificationResult) -> None:
        policy = SymlinkPolicy(SymlinkFilesMode.as_link)
        payload = policy.apply(symlink_entry, classification)
        assert isinstance(payload, LinkPayload)
        assert payload.link_target == "/target"

    def test_skip_returns_skipped_payload(self, symlink_entry: FileEntry, classification: ClassificationResult) -> None:
        policy = SymlinkPolicy(SymlinkFilesMode.skip)
        payload = policy.apply(symlink_entry, classification)
        assert isinstance(payload, SkippedPayload)
        assert payload.code == SkipCode.unknown
        # The message is generic, so we check the code and detail
        assert payload.detail == {"reason": "symlink_files_mode=skip"}

    def test_follow_returns_none(self, symlink_entry: FileEntry, classification: ClassificationResult) -> None:
        policy = SymlinkPolicy(SymlinkFilesMode.follow)
        payload = policy.apply(symlink_entry, classification)
        assert payload is None

    def test_regular_file_returns_none(self, regular_entry: FileEntry, classification: ClassificationResult) -> None:
        policy = SymlinkPolicy(SymlinkFilesMode.as_link)
        payload = policy.apply(regular_entry, classification)
        assert payload is None