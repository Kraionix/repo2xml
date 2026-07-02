# src/repo2xml/application/filters.py
from __future__ import annotations

from typing import List

from repo2xml.config import FilterConfig
from repo2xml.domain.model import FileEntry


def apply_file_filters(entries: List[FileEntry], filter_config: FilterConfig) -> List[FileEntry]:
    """
    Filter FileEntry list by size and mtime according to filter_config.

    Args:
        entries: List of file entries to filter.
        filter_config: Configuration containing size and time thresholds.

    Returns:
        Filtered list of file entries.
    """
    cfg = filter_config
    if (
        cfg.min_file_size > 0
        or cfg.max_file_size > 0
        or cfg.newer_than is not None
        or cfg.older_than is not None
    ):
        return [
            e
            for e in entries
            if (cfg.min_file_size == 0 or e.size >= cfg.min_file_size)
            and (cfg.max_file_size == 0 or e.size <= cfg.max_file_size)
            and (cfg.newer_than is None or (e.mtime_ns / 1e9) >= cfg.newer_than)
            and (cfg.older_than is None or (e.mtime_ns / 1e9) <= cfg.older_than)
        ]
    return entries