# tests/unit/application/test_processing_context.py
"""Unit tests for ProcessingContext."""

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from repo2xml.application.processing_context import ProcessingContext
from repo2xml.domain.model import FileEntry


class TestProcessingContext:
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

    def test_defaults(self, entry: FileEntry) -> None:
        ctx = ProcessingContext(entry=entry)
        assert ctx.entry is entry
        assert ctx.classification is None
        assert ctx.payload is None
        assert ctx.token_count is None
        assert ctx.should_stop is False
        assert ctx.is_success is False
        assert ctx.skip_code is None
        assert ctx.error_code is None
        assert ctx.message is None
        assert ctx.metadata == {}

    def test_set_fields(self, entry: FileEntry) -> None:
        ctx = ProcessingContext(entry=entry)
        ctx.classification = MagicMock()
        ctx.payload = MagicMock()
        ctx.token_count = 42
        ctx.should_stop = True
        ctx.is_success = True
        ctx.skip_code = "skip"
        ctx.error_code = "error"
        ctx.message = "msg"
        ctx.metadata["key"] = "value"

        assert ctx.classification is not None
        assert ctx.payload is not None
        assert ctx.token_count == 42
        assert ctx.should_stop is True
        assert ctx.is_success is True
        assert ctx.skip_code == "skip"
        assert ctx.error_code == "error"
        assert ctx.message == "msg"
        assert ctx.metadata == {"key": "value"}