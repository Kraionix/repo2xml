# tests/unit/application/steps/test_token_count_step.py
"""Unit tests for TokenCountStep."""

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from repo2xml.application.processing_context import ProcessingContext
from repo2xml.application.steps.token_count_step import TokenCountStep
from repo2xml.domain.model import FileEntry, TextPayload
from repo2xml.services.tokenize import TokenCounter


class TestTokenCountStep:
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

    def test_counts_tokens_text_payload(self, entry: FileEntry) -> None:
        mock_counter = MagicMock(spec=TokenCounter)
        mock_counter.count.return_value = 42

        step = TokenCountStep(mock_counter)
        ctx = ProcessingContext(entry=entry)
        original_payload = TextPayload(text="hello world", encoding="utf-8")
        ctx.payload = original_payload

        step.process(ctx)

        mock_counter.count.assert_called_once_with("hello world", ext=".txt")
        assert ctx.token_count == 42

    def test_ignores_non_text_payload(self, entry: FileEntry) -> None:
        mock_counter = MagicMock(spec=TokenCounter)
        step = TokenCountStep(mock_counter)
        ctx = ProcessingContext(entry=entry)
        ctx.payload = MagicMock()  # not TextPayload

        step.process(ctx)

        mock_counter.count.assert_not_called()
        assert ctx.token_count is None

    def test_handles_none_payload(self, entry: FileEntry) -> None:
        mock_counter = MagicMock(spec=TokenCounter)
        step = TokenCountStep(mock_counter)
        ctx = ProcessingContext(entry=entry)
        ctx.payload = None

        step.process(ctx)

        mock_counter.count.assert_not_called()
        assert ctx.token_count is None

    def test_error_does_not_stop(self, entry: FileEntry, caplog) -> None:
        mock_counter = MagicMock(spec=TokenCounter)
        mock_counter.count.side_effect = RuntimeError("tokenizer failed")

        step = TokenCountStep(mock_counter)
        ctx = ProcessingContext(entry=entry)
        ctx.payload = TextPayload(text="hello", encoding="utf-8")

        step.process(ctx)

        assert ctx.token_count is None
        # Should log a warning, but we don't check log content here.
        # The step catches exception and logs.
        assert ctx.should_stop is False
        assert ctx.is_success is False  # unchanged