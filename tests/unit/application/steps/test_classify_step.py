# tests/unit/application/steps/test_classify_step.py
"""Unit tests for ClassifyStep."""

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from repo2xml.application.steps.classify_step import ClassifyStep
from repo2xml.domain.model import ClassificationResult, FileEntry, ProcessingInput, ProcessingResult
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
        input = ProcessingInput(entry=entry)
        result = ProcessingResult()
        step.process(input, result)

        mock_engine.classify.assert_called_once_with(entry)
        assert result.classification is not None
        assert result.classification.kind == "text"
        assert result.should_stop is False
        assert result.is_success is False  # Not set here

    def test_error(self, entry: FileEntry) -> None:
        mock_engine = MagicMock(spec=ClassificationEngine)
        mock_engine.classify.return_value = ClassificationResult(kind="error", error="read failed")

        step = ClassifyStep(mock_engine)
        input = ProcessingInput(entry=entry)
        result = ProcessingResult()
        step.process(input, result)

        assert result.classification is not None
        assert result.classification.kind == "error"
        assert result.should_stop is True
        assert result.is_success is False
        assert result.error_code == "sniff_read_error"
        assert result.message == "read failed"