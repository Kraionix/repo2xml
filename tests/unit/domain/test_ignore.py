# tests/unit/domain/test_ignore.py
"""Unit tests for IgnoreRuleset domain model."""

import pytest

from pathspec.patterns.gitignore.spec import GitIgnoreSpecPattern

from repo2xml.domain.ignore import IgnoreRuleset


class TestIgnoreRuleset:
    def test_creation(self) -> None:
        patterns = (GitIgnoreSpecPattern("*.log"), GitIgnoreSpecPattern("!important.log"))
        ruleset = IgnoreRuleset(
            base_dir_rel="sub",
            base_prefix="sub/",
            patterns=patterns,
        )
        assert ruleset.base_dir_rel == "sub"
        assert ruleset.base_prefix == "sub/"
        assert ruleset.patterns == patterns
        assert len(ruleset.patterns) == 2

    def test_empty_patterns(self) -> None:
        ruleset = IgnoreRuleset(
            base_dir_rel="",
            base_prefix="",
            patterns=(),
        )
        assert ruleset.base_dir_rel == ""
        assert ruleset.base_prefix == ""
        assert ruleset.patterns == ()

    def test_patterns_tuple(self) -> None:
        # Ensure patterns is a tuple
        patterns = [GitIgnoreSpecPattern("*.tmp")]
        ruleset = IgnoreRuleset(
            base_dir_rel=".",
            base_prefix="./",
            patterns=tuple(patterns),
        )
        assert isinstance(ruleset.patterns, tuple)
        assert len(ruleset.patterns) == 1

    def test_frozen(self) -> None:
        ruleset = IgnoreRuleset(
            base_dir_rel="root",
            base_prefix="root/",
            patterns=(),
        )
        # Attempting to modify should raise AttributeError (slots=True)
        with pytest.raises(AttributeError):
            ruleset.base_dir_rel = "new"  # type: ignore