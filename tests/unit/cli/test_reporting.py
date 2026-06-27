# tests/unit/cli/test_reporting.py
"""Unit tests for CLI reporting helpers."""

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from repo2xml.cli.reporting import build_tree, print_breakdown
from repo2xml.domain.model import FileEntry


class TestPrintBreakdown:
    def test_empty_data(self):
        console = MagicMock()
        print_breakdown("Title", {}, console)
        console.print.assert_not_called()

    def test_non_empty_data(self):
        console = MagicMock()
        data = {"code1": 5, "code2": 3}
        print_breakdown("Title", data, console)
        # Check that table was created and printed
        console.print.assert_called_once()
        # We can't easily inspect the table, but we know it was called


class TestBuildTree:
    def test_empty_entries(self):
        console = MagicMock()
        entries = []
        build_tree(entries, console)
        console.print.assert_called_once()
        # The tree should have no children

    def test_entries(self):
        console = MagicMock()
        entries = [
            FileEntry(
                abs_path=Path("/a"),
                rel_path="file1.txt",
                name="file1.txt",
                size=0,
                mtime_ns=0,
                is_symlink=False,
            ),
            FileEntry(
                abs_path=Path("/a"),
                rel_path="sub/file2.py",
                name="file2.py",
                size=0,
                mtime_ns=0,
                is_symlink=False,
            ),
            FileEntry(
                abs_path=Path("/a"),
                rel_path="sub/dir/file3.py",
                name="file3.py",
                size=0,
                mtime_ns=0,
                is_symlink=False,
            ),
        ]
        build_tree(entries, console)
        console.print.assert_called_once()
        # We don't inspect the tree structure, just ensure it runs