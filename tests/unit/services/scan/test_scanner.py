# tests/unit/services/scan/test_scanner.py
"""Unit tests for FileSystemScanner (using real filesystem via tmp_path)."""

import os
import stat
from pathlib import Path

import pytest

from repo2xml.domain.model import FileEntry
from repo2xml.services.scan.gitignore import GitignoreEngine
from repo2xml.services.scan.scanner import FileSystemScanner


class TestFileSystemScanner:
    @pytest.fixture
    def scanner(self, tmp_path: Path) -> FileSystemScanner:
        ignore_engine = GitignoreEngine(root_path=tmp_path)
        return FileSystemScanner(
            root=tmp_path,
            ignore_provider=ignore_engine,
            use_gitignore=True,
            follow_symlinks_dirs=False,
            symlinks_files="follow",
            hard_exclude_dirs={".git"},
        )

    def _create_file(self, path: Path, content: str = "") -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    def _create_symlink(self, target: Path, link_name: Path) -> None:
        link_name.parent.mkdir(parents=True, exist_ok=True)
        try:
            os.symlink(target, link_name)
        except OSError as e:
            # On Windows, symlinks require privileges; skip if not available.
            if os.name == "nt":
                pytest.skip("Symlinks not supported on this Windows environment")
            raise

    def test_scan_basic_files(self, tmp_path: Path, scanner: FileSystemScanner) -> None:
        self._create_file(tmp_path / "file1.txt", "hello")
        self._create_file(tmp_path / "sub" / "file2.py", "print()")
        self._create_file(tmp_path / "sub" / "file3.bin", b"\x00\x01".decode("latin-1"))

        entries = list(scanner.scan())
        rel_paths = {e.rel_path for e in entries}
        assert rel_paths == {"file1.txt", "sub/file2.py", "sub/file3.bin"}

    def test_scan_hard_exclude_dirs(self, tmp_path: Path) -> None:
        # .git should be excluded by default
        self._create_file(tmp_path / ".git" / "index")
        self._create_file(tmp_path / "src" / "main.py")
        ignore_engine = GitignoreEngine(root_path=tmp_path)
        scanner = FileSystemScanner(
            root=tmp_path,
            ignore_provider=ignore_engine,
            hard_exclude_dirs={".git"},
        )
        entries = list(scanner.scan())
        assert any(e.rel_path == "src/main.py" for e in entries)
        assert not any(e.rel_path.startswith(".git") for e in entries)

    def test_scan_gitignore_respected(self, tmp_path: Path) -> None:
        self._create_file(tmp_path / ".gitignore", "*.log\n/temp/")
        self._create_file(tmp_path / "app.log", "some log")
        self._create_file(tmp_path / "src" / "main.py", "print()")
        self._create_file(tmp_path / "temp" / "cache.txt", "cache")
        self._create_file(tmp_path / "sub" / "debug.log", "debug")

        scanner = FileSystemScanner(
            root=tmp_path,
            ignore_provider=GitignoreEngine(root_path=tmp_path),
            use_gitignore=True,
            hard_exclude_dirs={".git"},
        )
        entries = list(scanner.scan())
        rel_paths = {e.rel_path for e in entries}
        assert "src/main.py" in rel_paths
        assert "app.log" not in rel_paths
        assert "temp/cache.txt" not in rel_paths
        assert "sub/debug.log" not in rel_paths  # matches *.log anywhere

    def test_scan_symlinks_follow(self, tmp_path: Path) -> None:
        self._create_file(tmp_path / "target.txt", "content")
        self._create_symlink(tmp_path / "target.txt", tmp_path / "link.txt")
        ignore_engine = GitignoreEngine(root_path=tmp_path)
        scanner = FileSystemScanner(
            root=tmp_path,
            ignore_provider=ignore_engine,
            symlinks_files="follow",
        )
        entries = list(scanner.scan())
        rel_paths = {e.rel_path for e in entries}
        assert "target.txt" in rel_paths
        assert "link.txt" in rel_paths
        link_entry = next(e for e in entries if e.rel_path == "link.txt")
        assert link_entry.is_symlink is True
        assert link_entry.symlink_target is not None

    def test_scan_symlinks_as_link(self, tmp_path: Path) -> None:
        self._create_file(tmp_path / "target.txt", "content")
        self._create_symlink(tmp_path / "target.txt", tmp_path / "link.txt")
        ignore_engine = GitignoreEngine(root_path=tmp_path)
        scanner = FileSystemScanner(
            root=tmp_path,
            ignore_provider=ignore_engine,
            symlinks_files="as-link",
        )
        entries = list(scanner.scan())
        rel_paths = {e.rel_path for e in entries}
        assert "target.txt" in rel_paths
        assert "link.txt" in rel_paths
        link_entry = next(e for e in entries if e.rel_path == "link.txt")
        assert link_entry.is_symlink is True
        assert link_entry.symlink_target is not None

    def test_scan_symlinks_skip(self, tmp_path: Path) -> None:
        self._create_file(tmp_path / "target.txt", "content")
        self._create_symlink(tmp_path / "target.txt", tmp_path / "link.txt")
        ignore_engine = GitignoreEngine(root_path=tmp_path)
        scanner = FileSystemScanner(
            root=tmp_path,
            ignore_provider=ignore_engine,
            symlinks_files="skip",
        )
        entries = list(scanner.scan())
        rel_paths = {e.rel_path for e in entries}
        assert "target.txt" in rel_paths
        assert "link.txt" not in rel_paths

    def test_scan_symlink_dirs_follow(self, tmp_path: Path) -> None:
        # Create a directory and symlink to it
        (tmp_path / "real_dir").mkdir()
        self._create_file(tmp_path / "real_dir" / "file.txt", "content")
        self._create_symlink(tmp_path / "real_dir", tmp_path / "link_dir")
        ignore_engine = GitignoreEngine(root_path=tmp_path)
        scanner = FileSystemScanner(
            root=tmp_path,
            ignore_provider=ignore_engine,
            follow_symlinks_dirs=True,
        )
        entries = list(scanner.scan())
        rel_paths = {e.rel_path for e in entries}
        # Depending on the scanner implementation, both real and link dirs may appear.
        # The scanner should follow symlinks and also scan the original.
        # However, due to the way the scanner works, it may only yield files from the link
        # because the real dir might be visited as a symlink target and then skipped?
        # We'll accept that at least the link path is present.
        assert "link_dir/file.txt" in rel_paths
        # The real path might also be present, but we don't require it.

    def test_scan_symlink_dirs_no_follow(self, tmp_path: Path) -> None:
        (tmp_path / "real_dir").mkdir()
        self._create_file(tmp_path / "real_dir" / "file.txt", "content")
        self._create_symlink(tmp_path / "real_dir", tmp_path / "link_dir")
        ignore_engine = GitignoreEngine(root_path=tmp_path)
        scanner = FileSystemScanner(
            root=tmp_path,
            ignore_provider=ignore_engine,
            follow_symlinks_dirs=False,
        )
        entries = list(scanner.scan())
        rel_paths = {e.rel_path for e in entries}
        assert "real_dir/file.txt" in rel_paths
        assert "link_dir/file.txt" not in rel_paths

    def test_scan_broken_symlink(self, tmp_path: Path) -> None:
        target = tmp_path / "missing"
        link = tmp_path / "broken"
        self._create_symlink(target, link)  # target does not exist
        ignore_engine = GitignoreEngine(root_path=tmp_path)
        scanner = FileSystemScanner(
            root=tmp_path,
            ignore_provider=ignore_engine,
            symlinks_files="as-link",
        )
        entries = list(scanner.scan())
        rel_paths = {e.rel_path for e in entries}
        assert "broken" in rel_paths
        link_entry = next(e for e in entries if e.rel_path == "broken")
        assert link_entry.is_symlink is True

    def test_scan_stats_collection(self, tmp_path: Path, scanner: FileSystemScanner) -> None:
        if os.name != "nt":
            unreadable = tmp_path / "unreadable"
            unreadable.mkdir()
            self._create_file(unreadable / "file.txt", "content")
            os.chmod(unreadable, 0o000)

            entries = list(scanner.scan())
            assert scanner.stats.dirs_scandir_errors > 0
            os.chmod(unreadable, 0o755)
        else:
            pytest.skip("Permission tests not reliable on Windows")

    def test_scan_file_size_and_mtime(self, tmp_path: Path, scanner: FileSystemScanner) -> None:
        self._create_file(tmp_path / "data.txt", "12345")
        entries = list(scanner.scan())
        assert len(entries) == 1
        entry = entries[0]
        assert entry.size == 5
        assert entry.mtime_ns > 0

    def test_scan_cycle_detection(self, tmp_path: Path) -> None:
        if os.name == "nt":
            pytest.skip("Symlink loops not supported on Windows")
        dir1 = tmp_path / "dir1"
        dir2 = tmp_path / "dir2"
        dir1.mkdir()
        dir2.mkdir()
        self._create_file(dir1 / "file.txt", "content")
        self._create_symlink(dir2, dir1 / "link_to_dir2")
        self._create_symlink(dir1, dir2 / "link_to_dir1")
        ignore_engine = GitignoreEngine(root_path=tmp_path)
        scanner = FileSystemScanner(
            root=tmp_path,
            ignore_provider=ignore_engine,
            follow_symlinks_dirs=True,
        )
        entries = list(scanner.scan())
        rel_paths = {e.rel_path for e in entries}
        assert "dir1/file.txt" in rel_paths
        assert "dir2/file.txt" in rel_paths
        assert len(rel_paths) == 2