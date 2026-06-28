# tests/unit/services/policies/test_mode_policy.py
"""Unit tests for ModePolicy."""

from pathlib import Path

import pytest

from repo2xml.config import Mode
from repo2xml.domain.model import ClassificationResult, FileEntry, MetadataPayload
from repo2xml.services.policies import ModePolicy


class TestModePolicy:
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
    def classification(self) -> ClassificationResult:
        return ClassificationResult(kind="text", encoding="utf-8")

    def test_metadata_mode_returns_metadata_payload(self, entry: FileEntry, classification: ClassificationResult) -> None:
        policy = ModePolicy(Mode.metadata)
        payload = policy.apply(entry, classification)
        assert isinstance(payload, MetadataPayload)

    def test_full_mode_returns_none(self, entry: FileEntry, classification: ClassificationResult) -> None:
        policy = ModePolicy(Mode.full)
        payload = policy.apply(entry, classification)
        assert payload is None

    def test_structure_mode_returns_none(self, entry: FileEntry, classification: ClassificationResult) -> None:
        policy = ModePolicy(Mode.structure)
        payload = policy.apply(entry, classification)
        assert payload is None