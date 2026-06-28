# tests/unit/services/scan/test_scan_stats.py
"""Unit tests for ScanStats."""

import pytest

from repo2xml.services.scan.scanner import ScanStats


class TestScanStats:
    def test_defaults(self) -> None:
        stats = ScanStats()
        assert stats.dirs_scandir_errors == 0
        assert stats.entry_is_symlink_errors == 0
        assert stats.entry_is_dir_errors == 0
        assert stats.entry_is_file_errors == 0
        assert stats.entry_stat_errors == 0
        assert stats.entry_readlink_errors == 0
        assert stats.errors_by_type == {}
        assert stats.error_examples == []

    def test_record_error(self) -> None:
        stats = ScanStats()
        stats.record_error("path/file.txt", PermissionError("Access denied"))
        assert stats.errors_by_type == {"PermissionError": 1}
        assert len(stats.error_examples) == 1
        assert stats.error_examples[0] == ("path/file.txt", "Access denied")

        stats.record_error("path/other.py", OSError("No such file"))
        assert stats.errors_by_type == {"PermissionError": 1, "OSError": 1}
        assert len(stats.error_examples) == 2

    def test_record_error_same_type(self) -> None:
        stats = ScanStats()
        stats.record_error("a", PermissionError("err1"))
        stats.record_error("b", PermissionError("err2"))
        assert stats.errors_by_type == {"PermissionError": 2}
        assert len(stats.error_examples) == 2

    def test_error_examples_limit(self) -> None:
        stats = ScanStats()
        # The default limit is 10
        for i in range(15):
            stats.record_error(f"file{i}.txt", Exception(f"error{i}"))
        assert len(stats.error_examples) == 10
        # Check that first 10 are kept
        assert stats.error_examples[0][0] == "file0.txt"
        assert stats.error_examples[-1][0] == "file9.txt"

    def test_has_issues_true_when_errors(self) -> None:
        stats = ScanStats()
        assert stats.has_issues() is False
        stats.record_error("a", Exception("err"))
        assert stats.has_issues() is True

    def test_has_issues_true_with_counters(self) -> None:
        stats = ScanStats()
        stats.dirs_scandir_errors = 1
        assert stats.has_issues() is True

    def test_summary_without_issues(self) -> None:
        stats = ScanStats()
        assert stats.summary() == "no issues"

    def test_summary_with_counters(self) -> None:
        stats = ScanStats()
        stats.dirs_scandir_errors = 2
        stats.entry_is_symlink_errors = 1
        stats.record_error("x", PermissionError("denied"))
        summary = stats.summary()
        assert "dirs_scandir_errors=2" in summary
        assert "entry_is_symlink_errors=1" in summary
        assert "by_type: PermissionError=1" in summary

    def test_summary_with_multiple_errors(self) -> None:
        stats = ScanStats()
        stats.record_error("a", PermissionError("denied"))
        stats.record_error("b", OSError("fail"))
        summary = stats.summary()
        assert "by_type: PermissionError=1, OSError=1" in summary or "by_type: OSError=1, PermissionError=1" in summary