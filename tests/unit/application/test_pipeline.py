# tests/unit/application/test_pipeline.py
"""Unit tests for Pipeline."""

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from repo2xml.application.pipeline import Pipeline
from repo2xml.application.step import Step
from repo2xml.domain.model import FileEntry, ProcessingInput, ProcessingResult


class TestPipeline:
    @pytest.fixture
    def entry(self) -> FileEntry:
        return FileEntry(
            abs_path=Path("/repo/file.txt"),
            rel_path="file.txt",
            name="file.txt",
            size=0,
            mtime_ns=0,
            is_symlink=False,
        )

    def test_execute_no_steps(self, entry: FileEntry) -> None:
        pipeline = Pipeline([])
        input = ProcessingInput(entry=entry)
        result = pipeline.execute(input)
        assert isinstance(result, ProcessingResult)
        assert result.should_stop is False

    def test_execute_steps_in_order(self, entry: FileEntry) -> None:
        step1 = MagicMock(spec=Step)
        step2 = MagicMock(spec=Step)

        pipeline = Pipeline([step1, step2])
        input = ProcessingInput(entry=entry)
        result = pipeline.execute(input)

        step1.process.assert_called_once_with(input, result)
        step2.process.assert_called_once_with(input, result)
        assert isinstance(result, ProcessingResult)

    def test_execute_stops_on_should_stop(self, entry: FileEntry) -> None:
        step1 = MagicMock(spec=Step)
        step2 = MagicMock(spec=Step)

        def side_effect(input: ProcessingInput, result: ProcessingResult) -> None:
            result.should_stop = True

        step1.process.side_effect = side_effect

        pipeline = Pipeline([step1, step2])
        input = ProcessingInput(entry=entry)
        result = pipeline.execute(input)

        step1.process.assert_called_once_with(input, result)
        step2.process.assert_not_called()
        assert result.should_stop is True