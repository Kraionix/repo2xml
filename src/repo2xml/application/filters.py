# src/repo2xml/application/filters.py
from __future__ import annotations

from typing import List

from repo2xml.config import ExportConfig
from repo2xml.domain.model import FileEntry


def apply_file_filters(entries: List[FileEntry], config: ExportConfig) -> List[FileEntry]:
    """
    Filter FileEntry list by size and mtime according to config.

    This is a pure function, intentionally extracted to be reused between
    the pipeline and the dry‑run facade method.
    """
    cfg = config.filter
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