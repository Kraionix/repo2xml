# tests/unit/test_config.py
"""Unit tests for configuration classes and validation."""

from pathlib import Path

import pytest

from repo2xml.config import (
    BinaryMode,
    ConfigurationError,
    DecodeErrors,
    ExportConfig,
    Formatting,
    Mode,
    NewlineMode,
    RestoreConfig,
    RootPathMode,
    SymlinkFilesMode,
)
from repo2xml.domain.exceptions import ConfigurationError as DomainConfigurationError


class TestExportConfigNormalize:
    def test_format_lowercase(self) -> None:
        cfg = ExportConfig(format="XML")
        cfg.normalize()
        assert cfg.format == "xml"

    def test_source_lowercase(self) -> None:
        cfg = ExportConfig(source="FileSystem")
        cfg.normalize()
        assert cfg.source == "filesystem"

    def test_hard_exclude_dirs_dedup(self) -> None:
        cfg = ExportConfig(hard_exclude_dirs=[".git", ".git", "node_modules"])
        cfg.normalize()
        assert cfg.hard_exclude_dirs == [".git", "node_modules"]

    def test_hard_exclude_dirs_preserves_order(self) -> None:
        cfg = ExportConfig(hard_exclude_dirs=["a", "b", "a"])
        cfg.normalize()
        assert cfg.hard_exclude_dirs == ["a", "b"]

    def test_empty_format_becomes_default(self) -> None:
        cfg = ExportConfig(format="")
        cfg.normalize()
        assert cfg.format == "xml"


class TestExportConfigValidate:
    def test_valid_config_passes(self) -> None:
        cfg = ExportConfig()
        cfg.normalize()
        cfg.validate()  # should not raise

    @pytest.mark.parametrize(
        "field,value",
        [
            ("max_text_size", -1),
            ("max_base64_size", -1),
            ("max_hash_size", -1),
            ("write_buffer_chars", -1),
            ("min_file_size", -1),
            ("max_file_size", -1),
        ],
    )
    def test_non_negative_values_required(self, field: str, value: int) -> None:
        cfg = ExportConfig(**{field: value})
        cfg.normalize()
        with pytest.raises(ConfigurationError):
            cfg.validate()

    def test_min_size_greater_than_max_size(self) -> None:
        cfg = ExportConfig(min_file_size=100, max_file_size=50)
        cfg.normalize()
        with pytest.raises(ConfigurationError, match="min_file_size must be <= max_file_size"):
            cfg.validate()

    def test_include_patterns_with_leading_exclamation(self) -> None:
        cfg = ExportConfig(include_patterns=["!exclude"])
        cfg.normalize()
        with pytest.raises(ConfigurationError, match="must not start with '!'"):
            cfg.validate()

    def test_empty_source_raises(self) -> None:
        cfg = ExportConfig(source="")
        cfg.normalize()
        with pytest.raises(ConfigurationError, match="source must not be empty"):
            cfg.validate()

    def test_classify_config_path_file_not_exists(self, monkeypatch) -> None:
        fake_path = Path("/nonexistent.yml")
        # Override Path.is_file globally to return False
        monkeypatch.setattr(Path, "is_file", lambda self: False)
        cfg = ExportConfig(classify_config_path=fake_path)
        cfg.normalize()
        with pytest.raises(ConfigurationError, match="Classify config file does not exist"):
            cfg.validate()

    def test_count_tokens_without_transformers(self, monkeypatch) -> None:
        cfg = ExportConfig(count_tokens=True)
        cfg.normalize()

        def mock_import(name, *args, **kwargs):
            if name == "transformers":
                raise ImportError("No module named 'transformers'")
            return __import__(name, *args, **kwargs)

        monkeypatch.setattr("builtins.__import__", mock_import)

        with pytest.raises(ConfigurationError, match="Token counting requires"):
            cfg.validate()


class TestRestoreConfig:
    def test_normalize(self) -> None:
        cfg = RestoreConfig(format="XML")
        cfg.normalize()
        assert cfg.format == "xml"

    def test_empty_format_becomes_default(self) -> None:
        cfg = RestoreConfig(format="")
        cfg.normalize()
        assert cfg.format == "xml"

    def test_validate_valid(self) -> None:
        cfg = RestoreConfig()
        cfg.normalize()
        cfg.validate()  # no error


class TestEnums:
    def test_mode_values(self) -> None:
        assert Mode.full == "full"
        assert Mode.metadata == "metadata"
        assert Mode.structure == "structure"

    def test_binary_mode_values(self) -> None:
        assert BinaryMode.skip == "skip"
        assert BinaryMode.base64 == "base64"
        assert BinaryMode.hash == "hash"

    def test_formatting_values(self) -> None:
        assert Formatting.compact == "compact"
        assert Formatting.pretty == "pretty"
        assert Formatting.minify == "minify"

    def test_root_path_mode_values(self) -> None:
        assert RootPathMode.absolute == "absolute"
        assert RootPathMode.relative == "relative"
        assert RootPathMode.redact == "redact"

    def test_newline_mode_values(self) -> None:
        assert NewlineMode.preserve == "preserve"
        assert NewlineMode.lf == "lf"

    def test_symlink_files_mode_values(self) -> None:
        assert SymlinkFilesMode.follow == "follow"
        assert SymlinkFilesMode.skip == "skip"
        assert SymlinkFilesMode.as_link == "as-link"

    def test_decode_errors_values(self) -> None:
        assert DecodeErrors.replace == "replace"
        assert DecodeErrors.strict == "strict"