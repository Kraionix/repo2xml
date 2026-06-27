# tests/unit/services/ingest/redact/test_models.py
"""Unit tests for redaction data models."""

from repo2xml.services.ingest.redact.models import RedactionStats, Rule


class TestRule:
    def test_creation(self) -> None:
        rule = Rule(
            name="test-rule",
            pattern=r"secret-\d+",
            replacement="<redacted>",
            groups=["api_keys"],
            enabled=True,
        )
        assert rule.name == "test-rule"
        assert rule.pattern == r"secret-\d+"
        assert rule.replacement == "<redacted>"
        assert rule.groups == ["api_keys"]
        assert rule.enabled is True

    def test_default_groups(self) -> None:
        rule = Rule(name="simple", pattern=".*", replacement="***")
        assert rule.groups == []

    def test_default_enabled(self) -> None:
        rule = Rule(name="simple", pattern=".*", replacement="***")
        assert rule.enabled is True


class TestRedactionStats:
    def test_defaults(self) -> None:
        stats = RedactionStats()
        assert stats.total_files_processed == 0
        assert stats.total_files_skipped == 0
        assert stats.total_matches == 0
        assert stats.matches_by_rule == {}

    def test_update(self) -> None:
        stats = RedactionStats()
        stats.total_files_processed = 10
        stats.total_files_skipped = 2
        stats.total_matches = 5
        stats.matches_by_rule["aws"] = 3
        stats.matches_by_rule["github"] = 2

        assert stats.total_files_processed == 10
        assert stats.total_files_skipped == 2
        assert stats.total_matches == 5
        assert stats.matches_by_rule == {"aws": 3, "github": 2}