# tests/unit/application/test_pipeline_orchestrator.py
"""Unit tests for PipelineOrchestrator."""

from pathlib import Path
from unittest.mock import MagicMock, call

import pytest

from repo2xml.application.entry_processor import EntryProcessor
from repo2xml.application.pipeline_orchestrator import PipelineOrchestrator
from repo2xml.application.statistics_collector import StatisticsCollector
from repo2xml.application.writer_coordinator import WriterCoordinator
from repo2xml.config import (
    ExportConfig,
    Mode,
    OutputFormatConfig,
    ScanConfig,
    FilterConfig,
    BinaryHandlingConfig,
    TextHandlingConfig,
)
from repo2xml.domain.model import FileEntry, TextPayload


class TestPipelineOrchestrator:
    @pytest.fixture
    def config(self) -> ExportConfig:
        return ExportConfig(
            mode=Mode.full,
            output=OutputFormatConfig(formatting="compact", include_mtime=True, include_size=True),
            scan=ScanConfig(),
            filter=FilterConfig(),
            binary=BinaryHandlingConfig(),
            text=TextHandlingConfig(),
        )

    @pytest.fixture
    def mock_scanner(self) -> MagicMock:
        scanner = MagicMock()
        scanner.scan.return_value = [
            FileEntry(
                abs_path=Path("/repo/a.txt"),
                rel_path="a.txt",
                name="a.txt",
                size=10,
                mtime_ns=0,
                is_symlink=False,
            ),
            FileEntry(
                abs_path=Path("/repo/b.txt"),
                rel_path="b.txt",
                name="b.txt",
                size=20,
                mtime_ns=0,
                is_symlink=False,
            ),
        ]
        scanner.stats = None
        return scanner

    @pytest.fixture
    def mock_processor(self) -> MagicMock:
        processor = MagicMock(spec=EntryProcessor)

        def process_side_effect(entry):
            result = MagicMock()
            result.status = "success"
            result.payload = TextPayload(text=f"content of {entry.name}", encoding="utf-8")
            result.token_count = 10
            result.skip_code = None
            result.error_code = None
            result.message = None
            return result

        processor.process.side_effect = process_side_effect
        return processor

    @pytest.fixture
    def mock_writer(self) -> MagicMock:
        writer = MagicMock(spec=WriterCoordinator)
        writer.__enter__ = MagicMock(return_value=writer)
        writer.__exit__ = MagicMock(return_value=False)
        return writer

    @pytest.fixture
    def mock_stats(self) -> MagicMock:
        return MagicMock(spec=StatisticsCollector)

    @pytest.fixture
    def mock_progress(self) -> MagicMock:
        return MagicMock()

    @pytest.fixture
    def orchestrator(self, config, mock_scanner, mock_processor, mock_writer, mock_stats, mock_progress) -> PipelineOrchestrator:
        return PipelineOrchestrator(
            config=config,
            scanner=mock_scanner,
            entry_processor=mock_processor,
            writer_coordinator=mock_writer,
            statistics_collector=mock_stats,
            progress_reporter=mock_progress,
            root_path=Path("/repo"),
        )

    def test_execute_full(self, orchestrator, mock_scanner, mock_processor, mock_writer, mock_stats) -> None:
        orchestrator.execute()
        mock_scanner.scan.assert_called_once()
        assert mock_processor.process.call_count == 2
        mock_writer.write_header.assert_called_once()
        mock_writer.write_structure.assert_called_once()
        mock_writer.write_files_open.assert_called_once_with("full")
        assert mock_writer.write_file.call_count == 2
        mock_writer.write_files_close.assert_called_once()
        mock_writer.write_statistics.assert_called_once()
        mock_writer.write_footer.assert_called_once()
        # Success records should be called for each file
        assert mock_stats.record_success.call_count == 2
        assert mock_stats.record_skipped.call_count == 0
        assert mock_stats.record_error.call_count == 0

    def test_execute_with_skipped(self, orchestrator, mock_processor, mock_stats) -> None:
        def process_side_effect(entry):
            if entry.name == "a.txt":
                result = MagicMock()
                result.status = "skipped"
                result.skip_code = "text_size_limit"
                result.message = "too large"
                result.payload = None
                return result
            else:
                result = MagicMock()
                result.status = "success"
                result.payload = TextPayload(text="b", encoding="utf-8")
                result.token_count = 5
                return result

        mock_processor.process.side_effect = process_side_effect
        orchestrator.execute()
        mock_stats.record_success.assert_called_once()
        mock_stats.record_skipped.assert_called_once_with("text_size_limit", "too large")
        mock_stats.record_error.assert_not_called()

    def test_execute_with_error(self, orchestrator, mock_processor, mock_stats) -> None:
        def process_side_effect(entry):
            result = MagicMock()
            result.status = "error"
            result.error_code = "stat_error"
            result.message = "stat failed"
            result.payload = None
            return result

        mock_processor.process.side_effect = process_side_effect
        orchestrator.execute()
        mock_stats.record_error.assert_has_calls(
            [call("stat_error", "stat failed"), call("stat_error", "stat failed")]
        )
        mock_stats.record_success.assert_not_called()
        mock_stats.record_skipped.assert_not_called()

    def test_execute_structure_mode(self, config, mock_scanner, mock_processor, mock_writer, mock_stats, mock_progress) -> None:
        config.mode = Mode.structure
        orchestrator = PipelineOrchestrator(
            config=config,
            scanner=mock_scanner,
            entry_processor=mock_processor,
            writer_coordinator=mock_writer,
            statistics_collector=mock_stats,
            progress_reporter=mock_progress,
            root_path=Path("/repo"),
        )
        orchestrator.execute()
        mock_writer.write_files_open.assert_not_called()
        mock_writer.write_file.assert_not_called()
        mock_writer.write_files_close.assert_not_called()
        mock_writer.write_statistics.assert_not_called()
        mock_writer.write_header.assert_called_once()
        mock_writer.write_structure.assert_called_once()
        mock_writer.write_footer.assert_called_once()

    def test_execute_stats_only(self, orchestrator, mock_writer) -> None:
        orchestrator.execute(stats_only=True)
        mock_writer.write_header.assert_not_called()
        mock_writer.write_structure.assert_not_called()
        mock_writer.write_files_open.assert_not_called()
        mock_writer.write_file.assert_not_called()
        mock_writer.write_files_close.assert_not_called()
        mock_writer.write_statistics.assert_not_called()
        mock_writer.write_footer.assert_not_called()

    def test_execute_scan_warnings(self, orchestrator, mock_scanner, mock_stats) -> None:
        stats = MagicMock()
        stats.has_issues.return_value = True
        stats.summary.return_value = "some warnings"
        stats.dirs_scandir_errors = 1
        stats.entry_is_symlink_errors = 0
        stats.entry_is_dir_errors = 0
        stats.entry_is_file_errors = 0
        stats.entry_stat_errors = 0
        stats.entry_readlink_errors = 0
        mock_scanner.stats = stats

        orchestrator.execute()
        orchestrator.progress.set_warning_count.assert_called_once_with(1)
        mock_stats.get_export_stats.assert_called_with("some warnings")

    def test_keyboard_interrupt(self, orchestrator, mock_processor, mock_writer) -> None:
        mock_processor.process.side_effect = KeyboardInterrupt()
        with pytest.raises(KeyboardInterrupt):
            orchestrator.execute()
        # The writer is closed automatically via context manager; we don't call .close() directly.
        # Instead we check that __exit__ was called.
        mock_writer.__exit__.assert_called()