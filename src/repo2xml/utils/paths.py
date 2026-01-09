from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from repo2xml.config import RootPathMode


def posix_relpath(path: Path, base: Path) -> Optional[str]:
    """
    Return a POSIX-style relative path (with '/') if possible, else None.

    This is best-effort and should not raise.
    """
    try:
        rel = os.path.relpath(path.resolve(), base.resolve())
        rel = rel.replace("\\", "/")
        return rel if rel else "."
    except Exception:
        return None


def try_relpath_posix(child: Path, root: Path) -> Optional[str]:
    """Return POSIX relative path if child is inside root, else None."""
    try:
        return child.resolve().relative_to(root.resolve()).as_posix()
    except Exception:
        return None


def format_root_path(root: Path, mode: RootPathMode) -> str:
    """
    Format meta.root_path according to config.

    Always uses POSIX separators for reproducibility.
    """
    if mode == RootPathMode.absolute:
        return root.as_posix()

    if mode == RootPathMode.relative:
        cwd = Path.cwd().resolve()
        rel = posix_relpath(root, cwd)
        if rel is not None:
            return rel
        return (root.name or ".").replace("\\", "/")

    if mode == RootPathMode.redact:
        return "<redacted>"

    # Defensive fallback
    return root.as_posix()