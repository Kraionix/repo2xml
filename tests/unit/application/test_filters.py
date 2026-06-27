# tests/unit/application/test_filters.py
"""Unit tests for file filtering logic."""

from pathlib import Path
from typing import List

import pytest

from repo2xml.application.filters import apply_file_filters
from repo2xml.config import ExportConfig
from repo2xml.domain.model import FileEntry


@pytest.fixture
def sample_entries() -> List[FileEntry]:
    """Create a list of FileEntry objects with various sizes and mtimes."""
    base = Path("/repo")
    entries = []
    # file1: size 100, mtime 1000 (1e9 ns = 1s)
    entries.append(
        FileEntry(
            abs_path=base / "file1.txt",
            rel_path="file1.txt",
            name="file1.txt",
            size=100,
            mtime_ns=1_000_000_000,
            is_symlink=False,
        )
    )
    # file2: size 200, mtime 2000
    entries.append(
        FileEntry(
            abs_path=base / "file2.txt",
            rel_path="file2.txt",
            name="file2.txt",
            size=200,
            mtime_ns=2_000_000_000,
            is_symlink=False,
        )
    )
    # file3: size 300, mtime 3000
    entries.append(
        FileEntry(
            abs_path=base / "file3.txt",
            rel_path="file3.txt",
            name="file3.txt",
            size=300,
            mtime_ns=3_000_000_000,
            is_symlink=False,
        )
    )
    return entries


class TestApplyFileFilters:
    def test_no_filters(self, sample_entries: List[FileEntry]) -> None:
        config = ExportConfig()
        filtered = apply_file_filters(sample_entries, config)
        assert len(filtered) == 3
        assert filtered == sample_entries

    def test_min_file_size(self, sample_entries: List[FileEntry]) -> None:
        config = ExportConfig(min_file_size=150)
        filtered = apply_file_filters(sample_entries, config)
        assert len(filtered) == 2
        assert all(e.size >= 150 for e in filtered)

    def test_max_file_size(self, sample_entries: List[FileEntry]) -> None:
        config = ExportConfig(max_file_size=250)
        filtered = apply_file_filters(sample_entries, config)
        assert len(filtered) == 2
        assert all(e.size <= 250 for e in filtered)

    def test_min_and_max_file_size(self, sample_entries: List[FileEntry]) -> None:
        config = ExportConfig(min_file_size=150, max_file_size=250)
        filtered = apply_file_filters(sample_entries, config)
        assert len(filtered) == 1
        assert filtered[0].size == 200

    def test_newer_than(self, sample_entries: List[FileEntry]) -> None:
        # newer_than = 2.5 seconds (mtime_ns / 1e9 > 2.5)
        config = ExportConfig(newer_than=2.5)
        filtered = apply_file_filters(sample_entries, config)
        # only file3 has mtime 3.0 > 2.5
        assert len(filtered) == 1
        assert filtered[0].rel_path == "file3.txt"

    def test_older_than(self, sample_entries: List[FileEntry]) -> None:
        # older_than = 2.5 seconds (mtime_ns / 1e9 < 2.5)
        config = ExportConfig(older_than=2.5)
        filtered = apply_file_filters(sample_entries, config)
        # file1 and file2 qualify
        assert len(filtered) == 2
        assert {e.rel_path for e in filtered} == {"file1.txt", "file2.txt"}

    def test_combine_filters(self, sample_entries: List[FileEntry]) -> None:
        config = ExportConfig(
            min_file_size=150,
            max_file_size=250,
            newer_than=1.5,
            older_than=2.5,
        )
        filtered = apply_file_filters(sample_entries, config)
        # file2: size 200, mtime 2.0 -> inside both time ranges
        assert len(filtered) == 1
        assert filtered[0].rel_path == "file2.txt"

    def test_no_entries(self) -> None:
        config = ExportConfig()
        filtered = apply_file_filters([], config)
        assert filtered == []

    def test_ignore_zero_filters(self, sample_entries: List[FileEntry]) -> None:
        # when min=0, max=0, no time filters, all pass
        config = ExportConfig(min_file_size=0, max_file_size=0)
        filtered = apply_file_filters(sample_entries, config)
        assert len(filtered) == 3