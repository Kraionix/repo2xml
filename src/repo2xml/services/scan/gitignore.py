from __future__ import annotations

from pathlib import Path
from typing import List, Optional

import pathspec

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


def _read_gitignore_lines(p: Path) -> list[str]:
    """
    Read a .gitignore file as text.

    - Uses utf-8-sig to tolerate BOM.
    - Uses errors="replace" to avoid failing on legacy encodings.
    - Strips empty lines and full-line comments.
    """
    try:
        raw = p.read_text(encoding="utf-8-sig", errors="replace").splitlines()
    except OSError:
        return []

    out: list[str] = []
    for line in raw:
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        out.append(s)
    return out


def _prefix_pattern(base_dir_rel: str, pat: str) -> str:
    """
    Prefix a directory-local gitignore rule into a repo-root-relative rule.

    The intent is to keep matching simple: we always match against repo-root-relative
    POSIX paths. To approximate gitignore scoping:
    - "/foo" is anchored to the directory containing the .gitignore (not to repo root)
    - "a/b" stays within that directory
    - "foo" (no slash) is matched at any depth inside that directory => dir/**/foo
    - "!..." negation is preserved.

    This is an approximation; Git has nuanced rules, but this is good enough for
    typical repository filtering.
    """
    neg = pat.startswith("!")
    if neg:
        pat = pat[1:]

    base = base_dir_rel.strip("/")
    if base == ".":
        base = ""

    if pat.startswith("/"):
        pat = pat[1:]
        pref = f"{base}/{pat}" if base else pat
    else:
        if base:
            if "/" in pat:
                pref = f"{base}/{pat}"
            else:
                pref = f"{base}/**/{pat}"
        else:
            pref = pat

    return ("!" if neg else "") + pref


class GitignoreEngine:
    """
    gitignore compilation utilities.

    This class does not walk the filesystem. The scanner reads .gitignore files
    on the fly and uses this engine to prefix/compile patterns efficiently.
    """

    def __init__(
        self,
        *,
        root_path: Path,
        user_ignore: Optional[List[str]] = None,
        user_include: Optional[List[str]] = None,
    ):
        self.root_path = root_path.resolve()

        patterns: list[str] = []
        patterns.extend(ALWAYS_IGNORE)

        if user_ignore:
            patterns.extend(user_ignore)

        if user_include:
            # "Include" is represented as a gitignore negation rule.
            patterns.extend([("!" + p) if not p.startswith("!") else p for p in user_include])

        self.base_patterns = patterns

        # Cache compiled specs:
        # key = (id(parent_spec), hash(tuple(local_rules)))
        self._child_spec_cache: dict[tuple[int, int], pathspec.PathSpec] = {}

    def compile(self, patterns: list[str]) -> pathspec.PathSpec:
        """Compile gitwildmatch patterns into a PathSpec."""
        return pathspec.PathSpec.from_lines("gitwildmatch", patterns)

    def read_dir_gitignore_prefixed(self, dir_abs: Path, dir_rel_posix: str) -> list[str]:
        """
        If dir_abs/.gitignore exists, read it and return repo-root-relative patterns.

        dir_rel_posix is the repo-root-relative directory path (POSIX) of dir_abs.
        """
        gi = dir_abs / ".gitignore"
        if not gi.exists():
            return []

        lines = _read_gitignore_lines(gi)
        if not lines:
            return []

        base = dir_rel_posix if dir_rel_posix else ""
        return [_prefix_pattern(base, line) for line in lines]

    def compile_child_cached(
        self,
        parent_spec: pathspec.PathSpec,
        local_prefixed_rules: list[str],
        combined_patterns: list[str],
    ) -> pathspec.PathSpec:
        """
        Compile a new spec for (parent_rules + local_rules), with a small cache.

        This cache helps when many directories share identical .gitignore contents.
        """
        local_hash = hash(tuple(local_prefixed_rules))
        key = (id(parent_spec), local_hash)
        cached = self._child_spec_cache.get(key)
        if cached is not None:
            return cached

        spec = self.compile(combined_patterns)
        self._child_spec_cache[key] = spec
        return spec