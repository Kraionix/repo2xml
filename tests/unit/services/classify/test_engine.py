# tests/unit/services/classify/test_engine.py
"""Unit tests for ClassificationEngine."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from repo2xml.domain.model import FileEntry
from repo2xml.services.classify.engine import ClassificationEngine


class TestClassificationEngine:
    @pytest.fixture
    def engine(self, tmp_path: Path) -> ClassificationEngine:
        return ClassificationEngine(root_path=tmp_path)

    @pytest.fixture
    def entry(self, tmp_path: Path) -> FileEntry:
        path = tmp_path / "file.txt"
        path.write_text("hello", encoding="utf-8")
        return FileEntry(
            abs_path=path,
            rel_path="file.txt",
            name="file.txt",
            size=5,
            mtime_ns=0,
            is_symlink=False,
        )

    @patch("repo2xml.services.classify.engine.load_config")
    def test_classify_text_extension(self, mock_load_config, tmp_path: Path, entry: FileEntry) -> None:
        mock_load_config.return_value = {
            "text_extensions": [".txt"],
            "binary_extensions": [".bin"],
            "compound_binary_suffixes": [],
            "binary_threshold": 0.30,
        }
        engine = ClassificationEngine(root_path=tmp_path)
        result = engine.classify(entry)
        assert result.kind == "text"
        assert result.encoding == "utf-8"
        stats = engine.get_stats()
        assert stats.total_files == 1
        assert stats.by_extension == 1
        assert stats.errors == 0

    @patch("repo2xml.services.classify.engine.load_config")
    def test_classify_binary_extension(self, mock_load_config, tmp_path: Path) -> None:
        mock_load_config.return_value = {
            "text_extensions": [".txt"],
            "binary_extensions": [".bin"],
            "compound_binary_suffixes": [],
            "binary_threshold": 0.30,
        }
        path = tmp_path / "data.bin"
        path.write_bytes(b"binary")
        entry = FileEntry(
            abs_path=path,
            rel_path="data.bin",
            name="data.bin",
            size=6,
            mtime_ns=0,
            is_symlink=False,
        )
        engine = ClassificationEngine(root_path=tmp_path)
        result = engine.classify(entry)
        assert result.kind == "binary"
        stats = engine.get_stats()
        assert stats.by_extension == 1
        assert stats.total_files == 1

    @patch("repo2xml.services.classify.engine.load_config")
    def test_classify_by_content_text(self, mock_load_config, tmp_path: Path) -> None:
        mock_load_config.return_value = {
            "text_extensions": [],
            "binary_extensions": [],
            "compound_binary_suffixes": [],
            "binary_threshold": 0.30,
        }
        path = tmp_path / "file.unknown"
        path.write_text("Hello, world!", encoding="utf-8")
        entry = FileEntry(
            abs_path=path,
            rel_path="file.unknown",
            name="file.unknown",
            size=13,
            mtime_ns=0,
            is_symlink=False,
        )
        engine = ClassificationEngine(root_path=tmp_path)
        result = engine.classify(entry)
        assert result.kind == "text"
        assert result.encoding is not None
        stats = engine.get_stats()
        assert stats.by_content == 1
        assert stats.total_files == 1

    @patch("repo2xml.services.classify.engine.load_config")
    def test_classify_by_content_binary_with_null(self, mock_load_config, tmp_path: Path) -> None:
        mock_load_config.return_value = {
            "text_extensions": [],
            "binary_extensions": [],
            "compound_binary_suffixes": [],
            "binary_threshold": 0.30,
        }
        path = tmp_path / "file.bin"
        path.write_bytes(b"Hello\x00World")
        entry = FileEntry(
            abs_path=path,
            rel_path="file.bin",
            name="file.bin",
            size=11,
            mtime_ns=0,
            is_symlink=False,
        )
        engine = ClassificationEngine(root_path=tmp_path)
        result = engine.classify(entry)
        assert result.kind == "binary"

    @patch("repo2xml.services.classify.engine.load_config")
    def test_classify_error_reading(self, mock_load_config, tmp_path: Path) -> None:
        mock_load_config.return_value = {
            "text_extensions": [],
            "binary_extensions": [],
            "compound_binary_suffixes": [],
            "binary_threshold": 0.30,
        }
        path = tmp_path / "nonexistent"
        entry = FileEntry(
            abs_path=path,
            rel_path="nonexistent",
            name="nonexistent",
            size=0,
            mtime_ns=0,
            is_symlink=False,
        )
        engine = ClassificationEngine(root_path=tmp_path)
        result = engine.classify(entry)
        assert result.kind == "error"
        assert result.error is not None
        stats = engine.get_stats()
        assert stats.errors == 1
        assert stats.total_files == 1

    @patch("repo2xml.services.classify.engine.load_config")
    def test_classify_with_user_config(self, mock_load_config, tmp_path: Path) -> None:
        config_path = tmp_path / "custom.yml"
        config_path.write_text("text_extensions: [.custom]", encoding="utf-8")
        mock_load_config.return_value = {
            "text_extensions": [".custom"],
            "binary_extensions": [],
            "compound_binary_suffixes": [],
            "binary_threshold": 0.30,
        }
        path = tmp_path / "file.custom"
        path.write_text("hello", encoding="utf-8")
        entry = FileEntry(
            abs_path=path,
            rel_path="file.custom",
            name="file.custom",
            size=5,
            mtime_ns=0,
            is_symlink=False,
        )
        engine = ClassificationEngine(root_path=tmp_path, config_path=config_path)
        result = engine.classify(entry)
        assert result.kind == "text"

    def test_stats_provider(self, engine: ClassificationEngine, entry: FileEntry) -> None:
        # Classify a file to update stats
        engine.classify(entry)
        stats = engine.get_stats()
        # Now stats is a ClassificationStats object, not a dict
        assert stats.total_files == 1
        assert stats.by_extension == 1
        assert stats.errors == 0