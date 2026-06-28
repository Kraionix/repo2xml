# tests/unit/application/steps/test_redact_step.py
"""Unit tests for RedactStep."""

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from repo2xml.application.processing_context import ProcessingContext
from repo2xml.application.steps.redact_step import RedactStep
from repo2xml.domain.model import FileEntry, TextPayload
from repo2xml.services.ingest.redact import RedactionEngine


class TestRedactStep:
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

    def test_redacts_text_payload(self, entry: FileEntry) -> None:
        mock_engine = MagicMock(spec=RedactionEngine)
        mock_engine.process.return_value = "redacted content"

        step = RedactStep(mock_engine)
        ctx = ProcessingContext(entry=entry)
        original_payload = TextPayload(text="secret content", encoding="utf-8")
        ctx.payload = original_payload

        step.process(ctx)

        mock_engine.process.assert_called_once_with(entry, "secret content")
        assert isinstance(ctx.payload, TextPayload)
        assert ctx.payload.text == "redacted content"
        assert ctx.payload.encoding == "utf-8"

    def test_ignores_non_text_payload(self, entry: FileEntry) -> None:
        mock_engine = MagicMock(spec=RedactionEngine)
        step = RedactStep(mock_engine)
        ctx = ProcessingContext(entry=entry)
        ctx.payload = MagicMock()  # not TextPayload

        step.process(ctx)

        mock_engine.process.assert_not_called()
        # Payload unchanged
        assert ctx.payload is not None

    def test_handles_none_payload(self, entry: FileEntry) -> None:
        mock_engine = MagicMock(spec=RedactionEngine)
        step = RedactStep(mock_engine)
        ctx = ProcessingContext(entry=entry)
        ctx.payload = None

        step.process(ctx)

        mock_engine.process.assert_not_called()
        assert ctx.payload is None