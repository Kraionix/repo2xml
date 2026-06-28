# src/repo2xml/services/ingest/redact/exclusion.py
"""Glob‑based file exclusion using pathspec (Git wildmatch syntax)."""
from __future__ import annotations

from pathspec import PathSpec


class ExclusionManager:
    """Decides whether a relative path should be skipped."""

    def __init__(self, patterns: list[str]) -> None:
        # Using 'gitignore' as pattern language (GitIgnoreSpecPattern under the hood)
        self._spec = PathSpec.from_lines('gitignore', patterns)

    def is_excluded(self, rel_path: str) -> bool:
        """Return True if the path matches any exclusion pattern."""
        return self._spec.match_file(rel_path)