# tests/unit/test_config.py
"""Unit tests for configuration classes and validation."""

from pathlib import Path

import pytest

from repo2xml.config import (
    BinaryHandlingConfig,
    BinaryMode,
    ClassifyConfig,
    DecodeErrors,
    ExportConfig,
    FilterConfig,
    Formatting,
    Mode,
    NewlineMode,
    OutputFormatConfig,
    RedactConfig,
    RestoreConfig,
    RootPathMode,
    ScanConfig,
    SymlinkFilesMode,
    TextHandlingConfig,
    TokenCountConfig,
)
from repo2xml.domain.exceptions import ConfigurationError


# ----------------------------------------------------------------------
# ScanConfig tests
# ----------------------------------------------------------------------

class TestScanConfigNormalize:
    def test_source_lowercase(self) -> None:
        cfg = ScanConfig(source="FileSystem")
        cfg.normalize()
        assert cfg.source == "filesystem"

    def test_hard_exclude_dirs_dedup(self) -> None:
        cfg = ScanConfig(hard_exclude_dirs=[".git", ".git", "node_modules"])
        cfg.normalize()
        assert cfg.hard_exclude_dirs == [".git", "node_modules"]

    def test_hard_exclude_dirs_preserves_order(self) -> None:
        cfg = ScanConfig(hard_exclude_dirs=["a", "b", "a"])
        cfg.normalize()
        assert cfg.hard_exclude_dirs == ["a", "b"]


class TestScanConfigValidate:
    def test_valid_config_passes(self) -> None:
        cfg = ScanConfig()
        cfg.validate()  # should not raise

    def test_empty_source_raises(self) -> None:
        cfg = ScanConfig(source="")
        with pytest.raises(ConfigurationError, match="source must not be empty"):
            cfg.validate()

    def test_include_patterns_with_leading_exclamation(self) -> None:
        cfg = ScanConfig(include_patterns=["!exclude"])
        with pytest.raises(ConfigurationError, match="must not start with '!'"):
            cfg.validate()


# ----------------------------------------------------------------------
# FilterConfig tests
# ----------------------------------------------------------------------

class TestFilterConfigValidate:
    def test_valid_config_passes(self) -> None:
        cfg = FilterConfig()
        cfg.validate()

    @pytest.mark.parametrize(
        "field,value",
        [
            ("min_file_size", -1),
            ("max_file_size", -1),
        ],
    )
    def test_non_negative_values_required(self, field: str, value: int) -> None:
        cfg = FilterConfig(**{field: value})
        with pytest.raises(ConfigurationError):
            cfg.validate()

    def test_min_size_greater_than_max_size(self) -> None:
        cfg = FilterConfig(min_file_size=100, max_file_size=50)
        with pytest.raises(ConfigurationError, match="min_file_size must be <= max_file_size"):
            cfg.validate()


# ----------------------------------------------------------------------
# OutputFormatConfig tests
# ----------------------------------------------------------------------

class TestOutputFormatConfigValidate:
    def test_valid_config_passes(self) -> None:
        cfg = OutputFormatConfig()
        cfg.validate()

    def test_write_buffer_chars_negative(self) -> None:
        cfg = OutputFormatConfig(write_buffer_chars=-1)
        with pytest.raises(ConfigurationError, match="write_buffer_chars must be >= 0"):
            cfg.validate()


# ----------------------------------------------------------------------
# BinaryHandlingConfig tests
# ----------------------------------------------------------------------

class TestBinaryHandlingConfigValidate:
    def test_valid_config_passes(self) -> None:
        cfg = BinaryHandlingConfig()
        cfg.validate()

    @pytest.mark.parametrize(
        "field,value",
        [
            ("max_base64_size", -1),
            ("max_hash_size", -1),
        ],
    )
    def test_non_negative_values_required(self, field: str, value: int) -> None:
        cfg = BinaryHandlingConfig(**{field: value})
        with pytest.raises(ConfigurationError):
            cfg.validate()


# ----------------------------------------------------------------------
# TextHandlingConfig tests
# ----------------------------------------------------------------------

class TestTextHandlingConfigValidate:
    def test_valid_config_passes(self) -> None:
        cfg = TextHandlingConfig()
        cfg.validate()

    def test_max_text_size_negative(self) -> None:
        cfg = TextHandlingConfig(max_text_size=-1)
        with pytest.raises(ConfigurationError, match="max_text_size must be >= 0"):
            cfg.validate()


# ----------------------------------------------------------------------
# RedactConfig tests
# ----------------------------------------------------------------------

class TestRedactConfigValidate:
    def test_valid_config_passes(self) -> None:
        cfg = RedactConfig()
        cfg.validate()

    def test_config_path_not_exists(self) -> None:
        cfg = RedactConfig(config_path=Path("/nonexistent.yml"))
        with pytest.raises(ConfigurationError, match="Redact config file does not exist"):
            cfg.validate()


# ----------------------------------------------------------------------
# ClassifyConfig tests
# ----------------------------------------------------------------------

class TestClassifyConfigValidate:
    def test_valid_config_passes(self) -> None:
        cfg = ClassifyConfig()
        cfg.validate()

    def test_config_path_not_exists(self) -> None:
        cfg = ClassifyConfig(config_path=Path("/nonexistent.yml"))
        with pytest.raises(ConfigurationError, match="Classify config file does not exist"):
            cfg.validate()


# ----------------------------------------------------------------------
# TokenCountConfig tests
# ----------------------------------------------------------------------

class TestTokenCountConfigValidate:
    def test_valid_config_passes(self) -> None:
        cfg = TokenCountConfig(enabled=False)
        cfg.validate()

    def test_enabled_without_transformers(self, monkeypatch) -> None:
        cfg = TokenCountConfig(enabled=True)

        def mock_import(name, *args, **kwargs):
            if name == "transformers":
                raise ImportError("No module named 'transformers'")
            return __import__(name, *args, **kwargs)

        monkeypatch.setattr("builtins.__import__", mock_import)

        with pytest.raises(ConfigurationError, match="Token counting requires"):
            cfg.validate()


# ----------------------------------------------------------------------
# ExportConfig (aggregator) tests
# ----------------------------------------------------------------------

class TestExportConfigNormalize:
    def test_format_lowercase(self) -> None:
        cfg = ExportConfig(format="XML")
        cfg.normalize()
        assert cfg.format == "xml"

    def test_empty_format_becomes_default(self) -> None:
        cfg = ExportConfig(format="")
        cfg.normalize()
        assert cfg.format == "xml"

    def test_delegates_to_scan_normalize(self) -> None:
        cfg = ExportConfig(scan=ScanConfig(source="FileSystem"))
        cfg.normalize()
        assert cfg.scan.source == "filesystem"


class TestExportConfigValidate:
    def test_valid_config_passes(self) -> None:
        cfg = ExportConfig()
        cfg.normalize()
        cfg.validate()  # should not raise

    def test_empty_format_after_normalize_is_valid(self) -> None:
        # Empty format is normalized to "xml", so validation should pass
        cfg = ExportConfig(format="")
        cfg.normalize()
        cfg.validate()  # no exception

    def test_delegates_to_scan_validation(self) -> None:
        cfg = ExportConfig(scan=ScanConfig(source=""))
        cfg.normalize()
        with pytest.raises(ConfigurationError, match="source must not be empty"):
            cfg.validate()

    def test_delegates_to_filter_validation(self) -> None:
        cfg = ExportConfig(filter=FilterConfig(min_file_size=100, max_file_size=50))
        cfg.normalize()
        with pytest.raises(ConfigurationError, match="min_file_size must be <= max_file_size"):
            cfg.validate()


# ----------------------------------------------------------------------
# RestoreConfig (unchanged)
# ----------------------------------------------------------------------

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


# ----------------------------------------------------------------------
# Enums (unchanged)
# ----------------------------------------------------------------------

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