# tests/unit/application/steps/test_classify_step.py
"""Unit tests for ClassifyStep."""

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from repo2xml.application.processing_context import ProcessingContext
from repo2xml.application.steps.classify_step import ClassifyStep
from repo2xml.domain.model import ClassificationResult, FileEntry
from repo2xml.services.classify import ClassificationEngine


class TestClassifyStep:
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

    def test_success(self, entry: FileEntry) -> None:
        mock_engine = MagicMock(spec=ClassificationEngine)
        mock_engine.classify.return_value = ClassificationResult(kind="text", encoding="utf-8")

        step = ClassifyStep(mock_engine)
        ctx = ProcessingContext(entry=entry)
        step.process(ctx)

        mock_engine.classify.assert_called_once_with(entry)
        assert ctx.classification is not None
        assert ctx.classification.kind == "text"
        assert ctx.should_stop is False
        assert ctx.is_success is False  # Not set here

    def test_error(self, entry: FileEntry) -> None:
        mock_engine = MagicMock(spec=ClassificationEngine)
        mock_engine.classify.return_value = ClassificationResult(kind="error", error="read failed")

        step = ClassifyStep(mock_engine)
        ctx = ProcessingContext(entry=entry)
        step.process(ctx)

        assert ctx.classification is not None
        assert ctx.classification.kind == "error"
        assert ctx.should_stop is True
        assert ctx.is_success is False
        assert ctx.error_code == "classification_error"
        assert ctx.message == "read failed"