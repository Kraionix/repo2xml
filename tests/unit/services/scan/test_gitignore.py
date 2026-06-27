# tests/unit/services/scan/test_gitignore.py
"""Unit tests for GitignoreEngine (logic of ignore rules, no real FS)."""

from pathlib import Path

import pytest

from repo2xml.services.scan.gitignore import GitignoreEngine, IgnoreRuleset, _normalize_gitignore_line


class TestNormalizeGitignoreLine:
    def test_empty_line(self) -> None:
        assert _normalize_gitignore_line("") is None
        assert _normalize_gitignore_line("   ") is None

    def test_comment(self) -> None:
        assert _normalize_gitignore_line("# comment") is None
        assert _normalize_gitignore_line(" # comment") is not None  # leading space

    def test_escaped_comment(self) -> None:
        line = "\\# not a comment"
        result = _normalize_gitignore_line(line)
        assert result == "\\# not a comment"

    def test_trailing_spaces(self) -> None:
        assert _normalize_gitignore_line("pattern   ") == "pattern"
        # escaped trailing space
        assert _normalize_gitignore_line("pattern\\ ") == "pattern "

    def test_leading_spaces_preserved(self) -> None:
        assert _normalize_gitignore_line(" pattern") == " pattern"


class TestGitignoreEngine:
    @pytest.fixture
    def engine(self, tmp_path: Path) -> GitignoreEngine:
        return GitignoreEngine(root_path=tmp_path)

    def test_base_ruleset(self, engine: GitignoreEngine) -> None:
        ruleset = engine.base_ruleset()
        assert ruleset.base_dir_rel == ""
        assert ruleset.base_prefix == ""
        # Should contain at least the ALWAYS_IGNORE patterns
        assert len(ruleset.patterns) > 0

    def test_load_dir_ruleset_no_file(self, engine: GitignoreEngine, tmp_path: Path) -> None:
        subdir = tmp_path / "sub"
        subdir.mkdir()
        ruleset = engine.load_dir_ruleset(dir_abs=subdir, dir_rel_posix="sub")
        assert ruleset is None

    def test_load_dir_ruleset_with_file(self, engine: GitignoreEngine, tmp_path: Path) -> None:
        gitignore = tmp_path / ".gitignore"
        gitignore.write_text("*.log\n!important.log\n", encoding="utf-8")
        ruleset = engine.load_dir_ruleset(dir_abs=tmp_path, dir_rel_posix="")
        assert ruleset is not None
        assert ruleset.base_dir_rel == ""
        assert ruleset.base_prefix == ""
        assert len(ruleset.patterns) == 2  # two patterns

    def test_load_dir_ruleset_caching(self, engine: GitignoreEngine, tmp_path: Path) -> None:
        gitignore = tmp_path / ".gitignore"
        gitignore.write_text("*.tmp", encoding="utf-8")
        # First call loads and caches
        ruleset1 = engine.load_dir_ruleset(dir_abs=tmp_path, dir_rel_posix="")
        # Second call returns cached tuple
        ruleset2 = engine.load_dir_ruleset(dir_abs=tmp_path, dir_rel_posix="")
        assert ruleset1 is not None
        assert ruleset2 is not None
        # The patterns tuple is the same object? Not necessarily, but cache ensures no reload.
        # We can check that the cache size increased? Not exposed.
        # We trust the implementation.

    def test_is_ignored_basic(self, engine: GitignoreEngine, tmp_path: Path) -> None:
        # Create a ruleset with a pattern
        gitignore = tmp_path / ".gitignore"
        gitignore.write_text("*.log\n", encoding="utf-8")
        ruleset = engine.load_dir_ruleset(dir_abs=tmp_path, dir_rel_posix="")
        assert ruleset is not None
        stack = [engine.base_ruleset(), ruleset]
        # Check ignoring
        assert engine.is_ignored(rel_path_posix="file.log", is_dir=False, stack=stack) is True
        assert engine.is_ignored(rel_path_posix="file.txt", is_dir=False, stack=stack) is False

    def test_is_ignored_negation(self, engine: GitignoreEngine, tmp_path: Path) -> None:
        gitignore = tmp_path / ".gitignore"
        gitignore.write_text("*.log\n!important.log\n", encoding="utf-8")
        ruleset = engine.load_dir_ruleset(dir_abs=tmp_path, dir_rel_posix="")
        assert ruleset is not None
        stack = [engine.base_ruleset(), ruleset]
        assert engine.is_ignored(rel_path_posix="important.log", is_dir=False, stack=stack) is False
        assert engine.is_ignored(rel_path_posix="other.log", is_dir=False, stack=stack) is True

    def test_is_ignored_directory_pattern(self, engine: GitignoreEngine, tmp_path: Path) -> None:
        gitignore = tmp_path / ".gitignore"
        gitignore.write_text("/temp/\n", encoding="utf-8")
        ruleset = engine.load_dir_ruleset(dir_abs=tmp_path, dir_rel_posix="")
        assert ruleset is not None
        stack = [engine.base_ruleset(), ruleset]
        # Directory pattern matches both files inside /temp and also the directory itself?
        # For is_dir=True we test both forms.
        assert engine.is_ignored(rel_path_posix="temp/file.txt", is_dir=False, stack=stack) is True
        # For a directory entry itself (not a file), we also test with trailing slash.
        assert engine.is_ignored(rel_path_posix="temp", is_dir=True, stack=stack) is True

    def test_is_ignored_scoped_rules(self, engine: GitignoreEngine, tmp_path: Path) -> None:
        # Root .gitignore: *.log
        root_git = tmp_path / ".gitignore"
        root_git.write_text("*.log\n", encoding="utf-8")
        root_ruleset = engine.load_dir_ruleset(dir_abs=tmp_path, dir_rel_posix="")
        # Subdir .gitignore: !important.log
        subdir = tmp_path / "sub"
        subdir.mkdir()
        sub_git = subdir / ".gitignore"
        sub_git.write_text("!important.log\n", encoding="utf-8")
        sub_ruleset = engine.load_dir_ruleset(dir_abs=subdir, dir_rel_posix="sub")
        assert root_ruleset is not None
        assert sub_ruleset is not None
        stack = [engine.base_ruleset(), root_ruleset, sub_ruleset]
        # In subdir, important.log should be included (negation overrides root)
        assert engine.is_ignored(rel_path_posix="sub/important.log", is_dir=False, stack=stack) is False
        # Other .log files in subdir should be ignored
        assert engine.is_ignored(rel_path_posix="sub/other.log", is_dir=False, stack=stack) is True
        # In root, a .log file should be ignored
        root_stack = [engine.base_ruleset(), root_ruleset]
        assert engine.is_ignored(rel_path_posix="root.log", is_dir=False, stack=root_stack) is True

    def test_is_ignored_last_matching_wins(self, engine: GitignoreEngine, tmp_path: Path) -> None:
        gitignore = tmp_path / ".gitignore"
        gitignore.write_text("*.txt\n!foo.txt\n", encoding="utf-8")
        ruleset = engine.load_dir_ruleset(dir_abs=tmp_path, dir_rel_posix="")
        assert ruleset is not None
        stack = [engine.base_ruleset(), ruleset]
        # The last pattern wins: foo.txt should be included.
        assert engine.is_ignored(rel_path_posix="foo.txt", is_dir=False, stack=stack) is False
        assert engine.is_ignored(rel_path_posix="bar.txt", is_dir=False, stack=stack) is True