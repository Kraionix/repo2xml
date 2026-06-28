# tests/unit/services/ingest/redact/test_engine.py
"""Unit tests for RedactionEngine."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from repo2xml.domain.model import FileEntry
from repo2xml.services.ingest.redact.engine import RedactionEngine


class TestRedactionEngine:
    @pytest.fixture
    def engine(self, tmp_path: Path) -> RedactionEngine:
        return RedactionEngine(root_path=tmp_path)

    @pytest.fixture
    def entry(self) -> FileEntry:
        return FileEntry(
            abs_path=Path("/dummy"),
            rel_path="file.txt",
            name="file.txt",
            size=0,
            mtime_ns=0,
            is_symlink=False,
        )

    def test_process_no_rules(self, engine: RedactionEngine, entry: FileEntry) -> None:
        text = "my password=secret"
        result = engine.process(entry, text)
        # Built-in generic-credential rule should catch "password=secret"
        assert "secret" not in result
        assert "<redacted:password>" in result

    @patch("repo2xml.services.ingest.redact.engine.load_rules")
    def test_process_with_custom_rules(self, mock_load_rules, tmp_path: Path, entry: FileEntry) -> None:
        from repo2xml.services.ingest.redact.models import Rule
        mock_rules = [
            Rule(name="custom", pattern=r"token-\d+", replacement="<REDACTED>"),
        ]
        mock_load_rules.return_value = mock_rules

        engine = RedactionEngine(root_path=tmp_path)
        engine._rules = mock_rules
        text = "my token-12345 is secret"
        result = engine.process(entry, text)
        assert "token-12345" not in result
        assert "<REDACTED>" in result

        # get_stats now returns a dict
        stats = engine.get_stats()
        assert stats.get("total_files_processed") == 1
        assert stats.get("total_matches") == 1
        assert stats.get("matches_by_rule", {}).get("custom") == 1

    def test_process_excluded_file(self, engine: RedactionEngine, entry: FileEntry) -> None:
        engine._exclusion = MagicMock()
        engine._exclusion.is_excluded.return_value = True
        text = "password=secret"
        result = engine.process(entry, text)
        assert result == text

        stats = engine.get_stats()
        assert stats.get("total_files_skipped") == 1
        assert stats.get("total_files_processed") == 0

    def test_get_stats(self, engine: RedactionEngine) -> None:
        stats = engine.get_stats()
        # get_stats returns a dict
        assert stats.get("total_files_processed") == 0
        assert stats.get("total_files_skipped") == 0
        assert stats.get("total_matches") == 0
        assert stats.get("matches_by_rule") == {}

    @patch("repo2xml.services.ingest.redact.engine.load_rules")
    def test_load_config_from_file(self, mock_load_rules, tmp_path: Path) -> None:
        config_path = tmp_path / ".repo2xml-redact.yml"
        config_path.write_text("rules: []", encoding="utf-8")
        engine = RedactionEngine(root_path=tmp_path)
        mock_load_rules.assert_called_once()

    @patch("repo2xml.services.ingest.redact.engine.load_rules")
    def test_load_config_explicit_path(self, mock_load_rules, tmp_path: Path) -> None:
        explicit = tmp_path / "custom.yml"
        explicit.write_text("rules: []", encoding="utf-8")
        engine = RedactionEngine(root_path=tmp_path, config_path=explicit)
        mock_load_rules.assert_called_once()