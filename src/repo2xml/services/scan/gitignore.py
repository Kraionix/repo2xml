# src/repo2xml/services/scan/gitignore.py
from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Sequence, Tuple

from pathspec.patterns.gitignore.spec import GitIgnoreSpecPattern

from repo2xml.domain.ignore import IgnoreRuleset

logger = logging.getLogger("repo2xml.gitignore")

ALWAYS_IGNORE = [
    ".idea",
    ".vscode",
    "__pycache__",
    "*.pyc",
    "*.pyo",
    ".DS_Store",
    "node_modules",
    "venv",
    ".env",
    ".venv",
    "*.egg-info",
    "dist",
    "build",
]


def _rstrip_unescaped_trailing_ws(s: str) -> str:
    if not s:
        return s
    out = s
    while out and out[-1] in (" ", "\t"):
        bs = 0
        i = len(out) - 2
        while i >= 0 and out[i] == "\\":
            bs += 1
            i -= 1
        if bs % 2 == 1:
            out = out[:-2] + out[-1]
            break
        out = out[:-1]
    return out


def _normalize_gitignore_line(raw: str) -> Optional[str]:
    if raw is None:
        return None
    line = raw[:-1] if raw.endswith("\r") else raw
    if line == "":
        return None
    if line.startswith("#") and not line.startswith("\\#"):
        return None
    line = _rstrip_unescaped_trailing_ws(line)
    if line == "":
        return None
    return line


def _read_gitignore_file_lines(p: Path) -> List[str]:
    try:
        return p.read_text(encoding="utf-8-sig", errors="replace").splitlines()
    except OSError:
        return []


def _compile_patterns(lines: Sequence[str], *, source: str = "<unknown>") -> Tuple[GitIgnoreSpecPattern, ...]:
    pats: List[GitIgnoreSpecPattern] = []
    for line in lines:
        norm = _normalize_gitignore_line(line)
        if not norm:
            continue
        try:
            pats.append(GitIgnoreSpecPattern(norm))
        except Exception:
            logger.warning("Invalid gitignore pattern in %s: %r", source, line)
            continue
    return tuple(pats)


class GitignoreEngine:
    """
    Gitignore engine implementing correct scoping (per-directory .gitignore).

    Scope rules (Git-compatible):
    - Patterns in a directory's .gitignore apply to that directory and its descendants.
    - Matching is performed against paths relative to the .gitignore directory.
    - "Last matching pattern wins" across all applicable .gitignore files.

    Implementation notes:
    - We use pathspec's GitIgnoreSpecPattern for correctness.
    - We do NOT consider Git index / tracked paths (not required).
    - We do NOT read any ignore files inside ".git" (scanner hard-excludes ".git").
    """

    def __init__(
        self,
        *,
        root_path: Path,
        user_ignore: Optional[List[str]] = None,
        user_include: Optional[List[str]] = None,
    ):
        self.root_path = root_path.resolve()

        base_lines: List[str] = []
        base_lines.extend(ALWAYS_IGNORE)
        if user_ignore:
            base_lines.extend(user_ignore)
        if user_include:
            for p in user_include:
                base_lines.append(p if p.startswith("!") else ("!" + p))

        self._base_ruleset = IgnoreRuleset(
            base_dir_rel="",
            base_prefix="",
            patterns=_compile_patterns(base_lines, source="<built-in rules>"),
        )

        # Cache: path -> (mtime, patterns)
        self._cache: dict[Path, Tuple[float, Tuple[GitIgnoreSpecPattern, ...]]] = {}

    def base_ruleset(self) -> IgnoreRuleset:
        return self._base_ruleset

    def load_dir_ruleset(self, *, dir_abs: Path, dir_rel_posix: str) -> Optional[IgnoreRuleset]:
        gi = dir_abs / ".gitignore"
        if not gi.exists():
            return None

        gi_path = gi.resolve()
        try:
            mtime = gi_path.stat().st_mtime
        except OSError:
            # If stat fails, treat as not found
            return None

        cached = self._cache.get(gi_path)
        if cached is not None and cached[0] == mtime:
            pats = cached[1]
        else:
            lines = _read_gitignore_file_lines(gi_path)
            pats = _compile_patterns(lines, source=str(gi_path))
            self._cache[gi_path] = (mtime, pats)

        if not pats:
            return None

        base = dir_rel_posix.strip("/")
        prefix = (base + "/") if base else ""

        return IgnoreRuleset(
            base_dir_rel=base,
            base_prefix=prefix,
            patterns=pats,
        )

    @staticmethod
    def _candidates(subpath: str, *, is_dir: bool) -> Tuple[str, ...]:
        if not is_dir:
            return (subpath,)
        if subpath.endswith("/"):
            return (subpath,)
        return (subpath, subpath + "/")

    def is_ignored(self, *, rel_path_posix: str, is_dir: bool, stack: Sequence[IgnoreRuleset]) -> bool:
        for ruleset in reversed(stack):
            prefix_len = len(ruleset.base_prefix)
            subpath = rel_path_posix[prefix_len:] if prefix_len else rel_path_posix
            candidates = self._candidates(subpath, is_dir=is_dir)
            for pat in reversed(ruleset.patterns):
                for cand in candidates:
                    try:
                        if pat.match_file(cand):
                            return bool(getattr(pat, "include", True))
                    except Exception:
                        continue
        return False