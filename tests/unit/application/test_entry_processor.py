# tests/unit/application/test_entry_processor.py
"""Unit tests for EntryProcessor with Pipeline."""

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from repo2xml.application.entry_processor import EntryProcessor
from repo2xml.application.pipeline import Pipeline
from repo2xml.application.processing_context import ProcessingContext
from repo2xml.application.process_result import ProcessResult
from repo2xml.domain.model import FileEntry, TextPayload


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
        # Arrange: pipeline will set ctx.is_success = True and provide payload
        def execute_side_effect(ctx: ProcessingContext) -> None:
            ctx.is_success = True
            ctx.payload = TextPayload(text="hello", encoding="utf-8")
            ctx.token_count = 42

        mock_pipeline.execute.side_effect = execute_side_effect

        processor = EntryProcessor(mock_pipeline)
        result = processor.process(entry)

        assert isinstance(result, ProcessResult)
        assert result.status == "success"
        assert isinstance(result.payload, TextPayload)
        assert result.payload.text == "hello"
        assert result.token_count == 42
        mock_pipeline.execute.assert_called_once()
        # Check that context was created with entry
        call_args = mock_pipeline.execute.call_args[0][0]
        assert call_args.entry is entry
        # The context now has payload because side_effect modified it; we don't check payload here.

    def test_process_skipped(self, mock_pipeline: MagicMock, entry: FileEntry) -> None:
        def execute_side_effect(ctx: ProcessingContext) -> None:
            ctx.is_success = False
            ctx.skip_code = "text_size_limit"
            ctx.message = "too large"

        mock_pipeline.execute.side_effect = execute_side_effect

        processor = EntryProcessor(mock_pipeline)
        result = processor.process(entry)

        assert result.status == "skipped"
        assert result.skip_code == "text_size_limit"
        assert result.message == "too large"
        assert result.payload is None
        assert result.token_count is None

    def test_process_error(self, mock_pipeline: MagicMock, entry: FileEntry) -> None:
        def execute_side_effect(ctx: ProcessingContext) -> None:
            ctx.is_success = False
            ctx.error_code = "stat_error"
            ctx.message = "stat failed"

        mock_pipeline.execute.side_effect = execute_side_effect

        processor = EntryProcessor(mock_pipeline)
        result = processor.process(entry)

        assert result.status == "error"
        assert result.error_code == "stat_error"
        assert result.message == "stat failed"
        assert result.payload is None
        assert result.token_count is None

    def test_process_fallback_error(self, mock_pipeline: MagicMock, entry: FileEntry) -> None:
        """If pipeline leaves no success/error/skip flags, fallback to error."""
        def execute_side_effect(ctx: ProcessingContext) -> None:
            # Nothing set
            pass

        mock_pipeline.execute.side_effect = execute_side_effect

        processor = EntryProcessor(mock_pipeline)
        result = processor.process(entry)

        assert result.status == "error"
        assert result.error_code == "unknown_error"
        assert result.message == "Processing failed"