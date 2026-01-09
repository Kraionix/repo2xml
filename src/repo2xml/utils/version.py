from __future__ import annotations

from importlib import metadata as importlib_metadata


def tool_version(dist_name: str = "repo2xml") -> str:
    """
    Best-effort read package version from importlib metadata.

    Kept as a tiny utility to avoid duplicated logic across CLI/pipeline layers.
    """
    try:
        return importlib_metadata.version(dist_name)
    except Exception:
        return "0.0.0"