# tests/unit/application/test_entry_processor.py
"""Unit tests for EntryProcessor with Pipeline."""

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from repo2xml.application.entry_processor import EntryProcessor
from repo2xml.application.pipeline import Pipeline
from repo2xml.application.process_result import ProcessResult
from repo2xml.domain.model import FileEntry, TextPayload, ProcessingInput, ProcessingResult


class TestEntryProcessor:
    @pytest.fixture
    def mock_pipeline(self) -> MagicMock:
        pipeline = MagicMock(spec=Pipeline)
        return pipeline

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

    def test_process_success(self, mock_pipeline: MagicMock, entry: FileEntry) -> None:
        # Arrange: pipeline will return a ProcessingResult with success
        result = ProcessingResult()
        result.is_success = True
        result.payload = TextPayload(text="hello", encoding="utf-8")
        result.token_count = 42

        mock_pipeline.execute.return_value = result

        processor = EntryProcessor(mock_pipeline)
        proc_result = processor.process(entry)

        assert isinstance(proc_result, ProcessResult)
        assert proc_result.status == "success"
        assert isinstance(proc_result.payload, TextPayload)
        assert proc_result.payload.text == "hello"
        assert proc_result.token_count == 42

        # Check that pipeline was called with ProcessingInput containing entry
        call_args = mock_pipeline.execute.call_args[0][0]
        assert isinstance(call_args, ProcessingInput)
        assert call_args.entry is entry

    def test_process_skipped(self, mock_pipeline: MagicMock, entry: FileEntry) -> None:
        result = ProcessingResult()
        result.is_success = False
        result.skip_code = "text_size_limit"
        result.message = "too large"

        mock_pipeline.execute.return_value = result

        processor = EntryProcessor(mock_pipeline)
        proc_result = processor.process(entry)

        assert proc_result.status == "skipped"
        assert proc_result.skip_code == "text_size_limit"
        assert proc_result.message == "too large"
        assert proc_result.payload is None
        assert proc_result.token_count is None

    def test_process_error(self, mock_pipeline: MagicMock, entry: FileEntry) -> None:
        result = ProcessingResult()
        result.is_success = False
        result.error_code = "stat_error"
        result.message = "stat failed"

        mock_pipeline.execute.return_value = result

        processor = EntryProcessor(mock_pipeline)
        proc_result = processor.process(entry)

        assert proc_result.status == "error"
        assert proc_result.error_code == "stat_error"
        assert proc_result.message == "stat failed"
        assert proc_result.payload is None
        assert proc_result.token_count is None

    def test_process_fallback_error(self, mock_pipeline: MagicMock, entry: FileEntry) -> None:
        """If pipeline returns no success/error/skip flags, fallback to error."""
        result = ProcessingResult()
        # Nothing set

        mock_pipeline.execute.return_value = result

        processor = EntryProcessor(mock_pipeline)
        proc_result = processor.process(entry)

        assert proc_result.status == "error"
        assert proc_result.error_code == "unknown_error"
        assert proc_result.message == "Processing failed"