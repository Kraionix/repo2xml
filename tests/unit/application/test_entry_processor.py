# tests/unit/application/test_entry_processor.py
"""Unit tests for EntryProcessor."""

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from repo2xml.application.entry_processor import EntryProcessor
from repo2xml.application.policies import ExportPayloadBuilder
from repo2xml.config import (
    BinaryHandlingConfig,
    BinaryMode,
    ExportConfig,
    Mode,
    RedactConfig,
    ScanConfig,
    TextHandlingConfig,
    TokenCountConfig,
)
from repo2xml.contracts import IngestorLike
from repo2xml.domain.model import (
    ClassificationResult,
    ErrorCode,
    FileEntry,
    SkipCode,
    TextPayload,
)


class TestEntryProcessor:
    @pytest.fixture
    def config(self) -> ExportConfig:
        return ExportConfig(
            mode=Mode.full,
            binary=BinaryHandlingConfig(mode=BinaryMode.skip),
            text=TextHandlingConfig(max_text_size=1000),
            token=TokenCountConfig(enabled=False),
            redact=RedactConfig(enabled=False),
            scan=ScanConfig(),
        )

    @pytest.fixture
    def mock_classifier(self) -> MagicMock:
        m = MagicMock()
        m.classify.return_value = ClassificationResult(kind="text", encoding="utf-8")
        return m

    @pytest.fixture
    def mock_ingestor(self) -> MagicMock:
        m = MagicMock(spec=IngestorLike)
        # Simulate successful text read
        read_result = MagicMock()
        read_result.kind = "text"
        read_result.text = "content"
        read_result.encoding = "utf-8"
        read_result.skipped = None
        read_result.error = None
        m.read_text.return_value = read_result
        return m

    @pytest.fixture
    def mock_redact(self) -> MagicMock:
        m = MagicMock()
        m.process.return_value = "redacted content"
        return m

    @pytest.fixture
    def mock_token_counter(self) -> MagicMock:
        m = MagicMock()
        m.count.return_value = 42
        return m

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

    def test_process_text_success(self, config, mock_classifier, mock_ingestor, entry) -> None:
        processor = EntryProcessor(
            config=config,
            ingestor=mock_ingestor,
            classification_engine=mock_classifier,
            redaction_engine=None,
            token_counter=None,
        )
        result = processor.process(entry)
        assert result.status == "success"
        assert isinstance(result.payload, TextPayload)
        assert result.payload.text == "content"
        assert result.token_count is None

    def test_process_with_token_counting(self, config, mock_classifier, mock_ingestor, mock_token_counter, entry) -> None:
        config.token.enabled = True
        processor = EntryProcessor(
            config=config,
            ingestor=mock_ingestor,
            classification_engine=mock_classifier,
            redaction_engine=None,
            token_counter=mock_token_counter,
        )
        result = processor.process(entry)
        assert result.status == "success"
        assert result.token_count == 42
        mock_token_counter.count.assert_called_once_with("content", ext=".txt")

    def test_process_with_redaction(self, config, mock_classifier, mock_ingestor, mock_redact, entry) -> None:
        config.redact.enabled = True
        processor = EntryProcessor(
            config=config,
            ingestor=mock_ingestor,
            classification_engine=mock_classifier,
            redaction_engine=mock_redact,
            token_counter=None,
        )
        result = processor.process(entry)
        assert result.status == "success"
        assert isinstance(result.payload, TextPayload)
        assert result.payload.text == "redacted content"
        mock_redact.process.assert_called_once_with(entry, "content")

    def test_process_classification_error(self, config, mock_classifier, mock_ingestor, entry) -> None:
        mock_classifier.classify.return_value = ClassificationResult(kind="error", error="read failed")
        processor = EntryProcessor(
            config=config,
            ingestor=mock_ingestor,
            classification_engine=mock_classifier,
            redaction_engine=None,
            token_counter=None,
        )
        result = processor.process(entry)
        assert result.status == "error"
        assert result.error_code == ErrorCode.sniff_read_error.value
        assert "read failed" in result.message

    def test_process_binary_skip(self, config, mock_classifier, mock_ingestor, entry) -> None:
        mock_classifier.classify.return_value = ClassificationResult(kind="binary")
        processor = EntryProcessor(
            config=config,
            ingestor=mock_ingestor,
            classification_engine=mock_classifier,
            redaction_engine=None,
            token_counter=None,
        )
        result = processor.process(entry)
        assert result.status == "skipped"
        assert result.skip_code == SkipCode.binary_skip_mode.value

    def test_process_text_size_limit(self, config, mock_classifier, mock_ingestor, entry) -> None:
        # Simulate ingestor returning skip
        read_result = MagicMock()
        read_result.kind = "skip"
        read_result.skipped = MagicMock(code=SkipCode.text_size_limit, detail={})
        mock_ingestor.read_text.return_value = read_result

        processor = EntryProcessor(
            config=config,
            ingestor=mock_ingestor,
            classification_engine=mock_classifier,
            redaction_engine=None,
            token_counter=None,
        )
        result = processor.process(entry)
        assert result.status == "skipped"
        assert result.skip_code == SkipCode.text_size_limit.value

    def test_process_text_read_error(self, config, mock_classifier, mock_ingestor, entry) -> None:
        read_result = MagicMock()
        read_result.kind = "error"
        read_result.error = MagicMock(code=ErrorCode.text_read_error, detail={})
        mock_ingestor.read_text.return_value = read_result

        processor = EntryProcessor(
            config=config,
            ingestor=mock_ingestor,
            classification_engine=mock_classifier,
            redaction_engine=None,
            token_counter=None,
        )
        result = processor.process(entry)
        assert result.status == "error"
        assert result.error_code == ErrorCode.text_read_error.value

    def test_process_tokenization_error(self, config, mock_classifier, mock_ingestor, mock_token_counter, entry) -> None:
        config.token.enabled = True
        mock_token_counter.count.side_effect = Exception("Tokenizer failed")
        processor = EntryProcessor(
            config=config,
            ingestor=mock_ingestor,
            classification_engine=mock_classifier,
            redaction_engine=None,
            token_counter=mock_token_counter,
        )
        result = processor.process(entry)
        assert result.status == "error"
        assert result.error_code == "tokenization_error"
        assert "Tokenizer failed" in result.message

    def test_process_unexpected_exception(self, config, mock_classifier, mock_ingestor, entry) -> None:
        mock_classifier.classify.side_effect = RuntimeError("Unexpected")
        processor = EntryProcessor(
            config=config,
            ingestor=mock_ingestor,
            classification_engine=mock_classifier,
            redaction_engine=None,
            token_counter=None,
        )
        result = processor.process(entry)
        assert result.status == "error"
        assert result.error_code == "processor_error"
        assert "Unexpected error" in result.message