# tests/unit/application/test_statistics_collector.py
"""Unit tests for StatisticsCollector."""

import pytest

from repo2xml.application.statistics_collector import StatisticsCollector
from repo2xml.domain.model import TokenStats
from repo2xml.services.scan.scanner import ScanStats


class TestStatisticsCollector:
    def test_defaults(self) -> None:
        collector = StatisticsCollector()
        stats = collector.get_export_stats()
        assert stats.files_total == 0
        assert stats.files_emitted == 0
        assert stats.files_skipped == 0
        assert stats.files_errors == 0
        assert stats.skipped_by_code == {}
        assert stats.errors_by_code == {}
        assert stats.token_stats is None
        assert stats.scan_stats is None

    def test_record_success(self) -> None:
        collector = StatisticsCollector()
        collector.record_success()
        stats = collector.get_export_stats()
        assert stats.files_emitted == 1
        assert stats.files_total == 1
        assert stats.files_skipped == 0
        assert stats.files_errors == 0

    def test_record_skipped(self) -> None:
        collector = StatisticsCollector()
        collector.record_skipped("text_size_limit", "too large")
        stats = collector.get_export_stats()
        assert stats.files_skipped == 1
        assert stats.skipped_by_code == {"text_size_limit": 1}
        assert stats.files_total == 1

    def test_record_error(self) -> None:
        collector = StatisticsCollector()
        collector.record_error("stat_error", "stat failed")
        stats = collector.get_export_stats()
        assert stats.files_errors == 1
        assert stats.errors_by_code == {"stat_error": 1}
        assert stats.files_total == 1

    def test_multiple_records(self) -> None:
        collector = StatisticsCollector()
        collector.record_success()
        collector.record_success()
        collector.record_skipped("text_size_limit")
        collector.record_error("stat_error")
        collector.record_error("stat_error")
        stats = collector.get_export_stats()
        assert stats.files_emitted == 2
        assert stats.files_skipped == 1
        assert stats.files_errors == 2
        assert stats.files_total == 5
        assert stats.skipped_by_code == {"text_size_limit": 1}
        assert stats.errors_by_code == {"stat_error": 2}

    def test_token_counting_disabled(self) -> None:
        collector = StatisticsCollector(token_counting_enabled=False)
        collector.record_success(token_count=100)
        stats = collector.get_export_stats()
        assert stats.token_stats is None

    def test_token_counting_enabled(self) -> None:
        collector = StatisticsCollector(token_counting_enabled=True)
        collector.record_success(token_count=100, ext=".py")
        collector.record_success(token_count=200, ext=".py")
        collector.record_success(token_count=50, ext=".txt")
        stats = collector.get_export_stats()
        assert stats.token_stats is not None
        ts = stats.token_stats
        assert ts.total_tokens == 350
        assert ts.files_processed == 3
        assert ts.tokens_by_extension == {".py": 300, ".txt": 50}
        assert ts.max_tokens == 200
        assert ts.min_tokens == 50
        assert ts.errors == 0
        assert ts.files_skipped == 0

    def test_token_counting_with_skipped(self) -> None:
        collector = StatisticsCollector(token_counting_enabled=True)
        collector.record_success(token_count=10)
        collector.record_skipped("size_limit")
        # Skipped files don't affect token stats
        stats = collector.get_export_stats()
        assert stats.token_stats.files_processed == 1
        assert stats.token_stats.total_tokens == 10

    def test_set_redaction_stats(self) -> None:
        collector = StatisticsCollector()
        mock_stats = object()
        collector.set_redaction_stats(mock_stats)
        stats = collector.get_export_stats()
        assert stats.redaction_stats is mock_stats

    def test_set_classification_stats(self) -> None:
        collector = StatisticsCollector()
        mock_stats = object()
        collector.set_classification_stats(mock_stats)
        stats = collector.get_export_stats()
        assert stats.classification_stats is mock_stats

    def test_set_scan_stats(self) -> None:
        collector = StatisticsCollector()
        scan_stats = ScanStats()
        collector.set_scan_stats(scan_stats)
        stats = collector.get_export_stats()
        assert stats.scan_stats is scan_stats

    def test_scan_warning_summary(self) -> None:
        collector = StatisticsCollector()
        stats = collector.get_export_stats("some scan warnings")
        assert stats.scan_warning_summary == "some scan warnings"

    def test_reset(self) -> None:
        collector = StatisticsCollector(token_counting_enabled=True)
        collector.record_success(token_count=100)
        collector.record_skipped("skip")
        collector.set_scan_stats(ScanStats())
        collector.reset()
        stats = collector.get_export_stats()
        assert stats.files_emitted == 0
        assert stats.files_skipped == 0
        assert stats.files_errors == 0
        assert stats.skipped_by_code == {}
        assert stats.errors_by_code == {}
        assert stats.token_stats.total_tokens == 0
        assert stats.token_stats.files_processed == 0
        assert stats.scan_stats is None