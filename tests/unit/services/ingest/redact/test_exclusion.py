# tests/unit/services/ingest/redact/test_exclusion.py
"""Unit tests for redaction exclusion manager."""

from repo2xml.services.ingest.redact.exclusion import ExclusionManager


class TestExclusionManager:
    def test_no_patterns(self) -> None:
        mgr = ExclusionManager([])
        assert mgr.is_excluded("file.txt") is False
        assert mgr.is_excluded("dir/file.txt") is False

    def test_simple_glob(self) -> None:
        mgr = ExclusionManager(["*.test.*", "tests/**"])
        assert mgr.is_excluded("file.test.py") is True
        assert mgr.is_excluded("file.txt") is False
        assert mgr.is_excluded("tests/unit/test_foo.py") is True
        assert mgr.is_excluded("src/main.py") is False

    def test_wildcard(self) -> None:
        mgr = ExclusionManager(["*.log"])
        assert mgr.is_excluded("access.log") is True
        assert mgr.is_excluded("logs/error.log") is True  # glob matches any path
        assert mgr.is_excluded("file.txt") is False

    def test_directory_pattern(self) -> None:
        mgr = ExclusionManager(["temp/"])
        assert mgr.is_excluded("temp/file.txt") is True
        assert mgr.is_excluded("temp/sub/file.txt") is True
        assert mgr.is_excluded("other/temp/file.txt") is True  # because pattern is "temp/", matches any temp directory
        # To match only root-level temp, use "/temp/", but pathspec's GitWildMatch handles this.
        # For simplicity we test that the pattern works.

    def test_negation(self) -> None:
        mgr = ExclusionManager(["*.py", "!main.py"])
        assert mgr.is_excluded("helper.py") is True
        assert mgr.is_excluded("main.py") is False  # negated

    def test_multiple_patterns(self) -> None:
        mgr = ExclusionManager(["*.tmp", "*.bak", "!important.bak"])
        assert mgr.is_excluded("file.tmp") is True
        assert mgr.is_excluded("file.bak") is True
        assert mgr.is_excluded("important.bak") is False