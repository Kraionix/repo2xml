# tests/unit/services/ingest/redact/test_rule_loader.py
"""Unit tests for redaction rule loader."""

from pathlib import Path
from unittest.mock import mock_open, patch

import pytest
import yaml

from repo2xml.services.ingest.redact.models import Rule
from repo2xml.services.ingest.redact.rule_loader import load_rules


class TestLoadRules:
    def test_load_builtin_only(self, tmp_path: Path) -> None:
        builtin_yaml = tmp_path / "builtin.yaml"
        builtin_yaml.write_text("""
rules:
  - name: rule1
    pattern: 'secret'
    replacement: '<redacted>'
    groups: ['api']
  - name: rule2
    pattern: 'token'
    replacement: '<token>'
    groups: ['tokens']
""", encoding="utf-8")
        rules = load_rules(builtin_yaml, None)
        assert len(rules) == 2
        assert rules[0].name == "rule1"
        assert rules[1].name == "rule2"

    def test_load_with_user_config_all_builtin(self, tmp_path: Path) -> None:
        builtin_yaml = tmp_path / "builtin.yaml"
        builtin_yaml.write_text("""
rules:
  - name: rule1
    pattern: 'secret'
    replacement: '<redacted>'
    groups: ['api']
  - name: rule2
    pattern: 'token'
    replacement: '<token>'
    groups: ['tokens']
""", encoding="utf-8")
        user_config = {"builtin_rules": "all"}
        rules = load_rules(builtin_yaml, user_config)
        assert len(rules) == 2

    def test_load_with_user_config_none_builtin(self, tmp_path: Path) -> None:
        builtin_yaml = tmp_path / "builtin.yaml"
        builtin_yaml.write_text("""
rules:
  - name: rule1
    pattern: 'secret'
    replacement: '<redacted>'
    groups: ['api']
  - name: rule2
    pattern: 'token'
    replacement: '<token>'
    groups: ['tokens']
""", encoding="utf-8")
        user_config = {"builtin_rules": "none"}
        rules = load_rules(builtin_yaml, user_config)
        assert len(rules) == 0

    def test_load_with_user_config_filter_groups(self, tmp_path: Path) -> None:
        builtin_yaml = tmp_path / "builtin.yaml"
        builtin_yaml.write_text("""
rules:
  - name: rule1
    pattern: 'secret'
    replacement: '<redacted>'
    groups: ['api']
  - name: rule2
    pattern: 'token'
    replacement: '<token>'
    groups: ['tokens']
""", encoding="utf-8")
        user_config = {"builtin_rules": ["api"]}
        rules = load_rules(builtin_yaml, user_config)
        assert len(rules) == 1
        assert rules[0].name == "rule1"

    def test_load_with_user_override(self, tmp_path: Path) -> None:
        builtin_yaml = tmp_path / "builtin.yaml"
        builtin_yaml.write_text("""
rules:
  - name: rule1
    pattern: 'secret'
    replacement: '<redacted>'
    groups: ['api']
""", encoding="utf-8")
        user_config = {
            "builtin_rules": "all",
            "rules": [
                {"name": "rule1", "pattern": "new", "replacement": "<NEW>"},
                {"name": "user_rule", "pattern": "user", "replacement": "<USER>"},
            ]
        }
        rules = load_rules(builtin_yaml, user_config)
        # rule1 is overridden, user_rule added
        assert len(rules) == 2
        rule_names = {r.name for r in rules}
        assert "rule1" in rule_names
        assert "user_rule" in rule_names
        # Check that rule1 has the new pattern
        rule1 = next(r for r in rules if r.name == "rule1")
        assert rule1.pattern == "new"
        assert rule1.replacement == "<NEW>"

    def test_load_with_disabled_user_rule(self, tmp_path: Path) -> None:
        builtin_yaml = tmp_path / "builtin.yaml"
        builtin_yaml.write_text("""
rules:
  - name: rule1
    pattern: 'secret'
    replacement: '<redacted>'
""", encoding="utf-8")
        user_config = {
            "builtin_rules": "all",
            "rules": [
                {"name": "rule1", "enabled": False},
            ]
        }
        rules = load_rules(builtin_yaml, user_config)
        assert len(rules) == 0

    def test_load_invalid_user_rule_missing_name(self, tmp_path: Path) -> None:
        builtin_yaml = tmp_path / "builtin.yaml"
        builtin_yaml.write_text("rules: []", encoding="utf-8")
        user_config = {
            "rules": [
                {"pattern": "foo", "replacement": "bar"}  # missing name
            ]
        }
        with pytest.raises(ValueError, match="missing a 'name'"):
            load_rules(builtin_yaml, user_config)

    def test_load_user_rule_missing_pattern(self, tmp_path: Path) -> None:
        builtin_yaml = tmp_path / "builtin.yaml"
        builtin_yaml.write_text("rules: []", encoding="utf-8")
        user_config = {
            "rules": [
                {"name": "test"}  # missing pattern and replacement
            ]
        }
        with pytest.raises(ValueError, match="must have 'pattern' and 'replacement'"):
            load_rules(builtin_yaml, user_config)