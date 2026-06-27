# tests/unit/services/classify/test_rule_loader.py
"""Unit tests for classification rule loader."""

from pathlib import Path
from unittest.mock import mock_open, patch

import pytest
import yaml

from repo2xml.services.classify.rule_loader import load_config


class TestLoadConfig:
    def test_load_builtin_only(self, tmp_path: Path) -> None:
        builtin_yaml = tmp_path / "builtin.yaml"
        builtin_yaml.write_text("""
text_extensions: [.txt, .py]
binary_extensions: [.bin]
compound_binary_suffixes: [.tar.gz]
binary_threshold: 0.30
""", encoding="utf-8")
        config = load_config(builtin_yaml, None)
        assert config["text_extensions"] == [".txt", ".py"]
        assert config["binary_extensions"] == [".bin"]
        assert config["compound_binary_suffixes"] == [".tar.gz"]
        assert config["binary_threshold"] == 0.30

    def test_load_with_user_full_override(self, tmp_path: Path) -> None:
        builtin_yaml = tmp_path / "builtin.yaml"
        builtin_yaml.write_text("""
text_extensions: [.txt, .py]
binary_extensions: [.bin]
compound_binary_suffixes: [.tar.gz]
binary_threshold: 0.30
""", encoding="utf-8")
        user_yaml = tmp_path / "user.yaml"
        user_yaml.write_text("""
text_extensions: [.custom]
binary_extensions: [.custom_bin]
compound_binary_suffixes: [.custom.tar]
binary_threshold: 0.50
""", encoding="utf-8")
        config = load_config(builtin_yaml, user_yaml)
        assert config["text_extensions"] == [".custom"]
        assert config["binary_extensions"] == [".custom_bin"]
        assert config["compound_binary_suffixes"] == [".custom.tar"]
        assert config["binary_threshold"] == 0.50

    def test_load_with_user_add_remove(self, tmp_path: Path) -> None:
        builtin_yaml = tmp_path / "builtin.yaml"
        builtin_yaml.write_text("""
text_extensions: [.txt, .py, .md]
binary_extensions: [.bin]
compound_binary_suffixes: [.tar.gz]
binary_threshold: 0.30
""", encoding="utf-8")
        user_yaml = tmp_path / "user.yaml"
        user_yaml.write_text("""
text_ext_add: [.custom, .new]
text_ext_remove: [.md]
binary_ext_add: [.custom_bin]
binary_ext_remove: [.bin]
compound_binary_add: [.new.tar]
compound_binary_remove: [.tar.gz]
""", encoding="utf-8")
        config = load_config(builtin_yaml, user_yaml)
        # Text: built-in [.txt, .py, .md] + .custom, .new - .md = [.txt, .py, .custom, .new]
        expected_text = [".txt", ".py", ".md", ".custom", ".new"]
        # But remove .md
        expected_text.remove(".md")
        assert sorted(config["text_extensions"]) == sorted(expected_text)
        # Binary: built-in [.bin] + .custom_bin - .bin = [.custom_bin]
        assert config["binary_extensions"] == [".custom_bin"]
        # Compound: [.tar.gz] + .new.tar - .tar.gz = [.new.tar]
        assert config["compound_binary_suffixes"] == [".new.tar"]
        # Threshold unchanged
        assert config["binary_threshold"] == 0.30

    def test_load_with_user_add_no_remove(self, tmp_path: Path) -> None:
        builtin_yaml = tmp_path / "builtin.yaml"
        builtin_yaml.write_text("""
text_extensions: [.txt]
""", encoding="utf-8")
        user_yaml = tmp_path / "user.yaml"
        user_yaml.write_text("""
text_ext_add: [.py]
""", encoding="utf-8")
        config = load_config(builtin_yaml, user_yaml)
        assert config["text_extensions"] == [".txt", ".py"]

    def test_load_with_user_remove_only(self, tmp_path: Path) -> None:
        builtin_yaml = tmp_path / "builtin.yaml"
        builtin_yaml.write_text("""
text_extensions: [.txt, .py, .md]
""", encoding="utf-8")
        user_yaml = tmp_path / "user.yaml"
        user_yaml.write_text("""
text_ext_remove: [.py]
""", encoding="utf-8")
        config = load_config(builtin_yaml, user_yaml)
        assert config["text_extensions"] == [".txt", ".md"]

    def test_load_with_invalid_yaml(self, tmp_path: Path) -> None:
        builtin_yaml = tmp_path / "builtin.yaml"
        builtin_yaml.write_text("""
text_extensions: [.txt]
""", encoding="utf-8")
        user_yaml = tmp_path / "user.yaml"
        user_yaml.write_text("invalid: yaml: [", encoding="utf-8")
        with pytest.raises(yaml.YAMLError):
            load_config(builtin_yaml, user_yaml)