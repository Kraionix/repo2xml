from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Sequence, Tuple

# We rely on pathspec's gitwildmatch matcher (existing dependency).
# Using compiled pattern objects directly allows correct per-directory scoping
# without lossy "prefix rewriting".
try:
    from pathspec.patterns.gitwildmatch import GitWildMatchPattern as _GitWildMatchPattern
except Exception:  # pragma: no cover
    # Fallback for older pathspec layouts (best-effort).
    from pathspec.patterns import GitWildMatchPattern as _GitWildMatchPattern  # type: ignore


# Patterns always ignored (noise reduction). These are soft ignores:
# a later negation pattern (e.g., "!...") could re-include them if desired.
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


@dataclass(slots=True, frozen=True)
class IgnoreRuleset:
    """
    A compiled ignore ruleset with a base directory scope.

    base_dir_rel:
      - POSIX path relative to repo root ("" for root)
    base_prefix:
      - base_dir_rel + "/" ("" for root), used for fast subpath derivation
    patterns:
      - compiled gitwildmatch patterns in original file order
    """
    base_dir_rel: str
    base_prefix: str
    patterns: Tuple[_GitWildMatchPattern, ...]


def _rstrip_unescaped_trailing_ws(s: str) -> str:
    """
    Strip trailing spaces/tabs unless the final whitespace is escaped with a backslash.

    Git semantics (practical subset):
    - Trailing spaces are ignored.
    - A trailing space can be made significant by escaping it with a backslash: "foo\\ ".
      In that case, the escaping backslash is removed but the space is kept.
    """
    if not s:
        return s

    out = s
    while out and out[-1] in (" ", "\t"):
        # Count backslashes immediately before the trailing whitespace.
        bs = 0
        i = len(out) - 2
        while i >= 0 and out[i] == "\\":
            bs += 1
            i -= 1

        if bs % 2 == 1:
            # Whitespace is escaped: drop one backslash and keep the whitespace.
            out = out[:-2] + out[-1]
            break

        # Unescaped trailing whitespace: strip it.
        out = out[:-1]

    return out


def _normalize_gitignore_line(raw: str) -> Optional[str]:
    """
    Normalize a single .gitignore line to a pattern string.

    Key Git parsing rules implemented:
    - Empty lines are ignored.
    - Lines starting with '#' are comments (unless escaped as '\\#').
    - Trailing spaces/tabs are ignored unless escaped with a backslash.

    Important:
    - We intentionally do NOT strip leading whitespace. Leading spaces can be significant.
    - We do NOT unescape leading '\\!' or '\\#' here; the gitwildmatch matcher supports
      Git-style escaping. Unescaping '\\!' would be incorrect (it would turn a literal
      '!' into a negation marker).
    """
    if raw is None:
        return None

    # Drop trailing CR from CRLF files. splitlines() usually handles this, but keep safe.
    line = raw[:-1] if raw.endswith("\r") else raw

    if line == "":
        return None

    # Comment handling: '#' at the beginning starts a comment, unless escaped.
    if line.startswith("#") and not line.startswith("\\#"):
        return None

    # Trailing whitespace normalization.
    line = _rstrip_unescaped_trailing_ws(line)

    if line == "":
        return None

    return line


def _read_gitignore_file_lines(p: Path) -> List[str]:
    """
    Read a .gitignore file as text.

    - Uses utf-8-sig to tolerate BOM.
    - Uses errors="replace" to avoid failing on legacy encodings.
    """
    try:
        return p.read_text(encoding="utf-8-sig", errors="replace").splitlines()
    except OSError:
        return []


def _compile_patterns(lines: Sequence[str]) -> Tuple[_GitWildMatchPattern, ...]:
    """
    Compile normalized gitignore lines into gitwildmatch pattern objects.

    We keep compilation isolated to allow caching and to avoid repeated parsing.
    """
    pats: List[_GitWildMatchPattern] = []
    for line in lines:
        norm = _normalize_gitignore_line(line)
        if not norm:
            continue
        try:
            pats.append(_GitWildMatchPattern(norm))
        except Exception:
            # Best-effort: skip patterns that the matcher cannot compile.
            # Git itself ignores some malformed patterns.
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
    - We use pathspec's gitwildmatch matcher (pattern objects) for correctness.
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
            # "Include" is represented as a gitignore negation rule.
            for p in user_include:
                base_lines.append(p if p.startswith("!") else ("!" + p))

        self._base_ruleset = IgnoreRuleset(
            base_dir_rel="",
            base_prefix="",
            patterns=_compile_patterns(base_lines),
        )

        # Cache compiled pattern tuples for .gitignore files (keyed by absolute path).
        self._compiled_cache: dict[Path, Tuple[_GitWildMatchPattern, ...]] = {}

    def base_ruleset(self) -> IgnoreRuleset:
        """Return the root-scoped base ruleset (ALWAYS_IGNORE + user overrides)."""
        return self._base_ruleset

    def load_dir_ruleset(self, *, dir_abs: Path, dir_rel_posix: str) -> Optional[IgnoreRuleset]:
        """
        Load and compile dir_abs/.gitignore (if it exists) into a scoped ruleset.

        dir_rel_posix:
          repo-root-relative directory path using POSIX separators ("" for root).
        """
        gi = dir_abs / ".gitignore"
        if not gi.exists():
            return None

        gi_path = gi.resolve()
        pats = self._compiled_cache.get(gi_path)
        if pats is None:
            lines = _read_gitignore_file_lines(gi)
            pats = _compile_patterns(lines)
            self._compiled_cache[gi_path] = pats

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
        """
        Return candidate path strings for matching.

        Directory-only patterns typically require a trailing slash to match reliably,
        so for directories we test both forms.
        """
        if not is_dir:
            return (subpath,)
        if subpath.endswith("/"):
            return (subpath,)
        return (subpath, subpath + "/")

    def is_ignored(self, *, rel_path_posix: str, is_dir: bool, stack: Sequence[IgnoreRuleset]) -> bool:
        """
        Determine whether a path is ignored under the current ignore stack.

        rel_path_posix:
          repo-root-relative path using POSIX separators (no leading slash).

        The stack must contain rulesets from root to current directory (in that order).
        """
        # Iterate rulesets from deepest to root: last match wins.
        for ruleset in reversed(stack):
            # Defensive: ensure the ruleset scope contains the target.
            if ruleset.base_prefix and not rel_path_posix.startswith(ruleset.base_prefix):
                continue

            subpath = rel_path_posix[len(ruleset.base_prefix) :] if ruleset.base_prefix else rel_path_posix
            candidates = self._candidates(subpath, is_dir=is_dir)

            # Iterate patterns from bottom to top: last matching pattern wins.
            for pat in reversed(ruleset.patterns):
                for cand in candidates:
                    try:
                        if pat.match_file(cand):
                            # In pathspec gitwildmatch:
                            # - non-negated patterns typically have include=True (ignored)
                            # - negated patterns typically have include=False (not ignored)
                            return bool(getattr(pat, "include", True))
                    except Exception:
                        # Best-effort: ignore matcher failures for this pattern.
                        continue

        return False