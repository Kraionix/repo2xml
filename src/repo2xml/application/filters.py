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
    if (
        config.min_file_size > 0
        or config.max_file_size > 0
        or config.newer_than is not None
        or config.older_than is not None
    ):
        return [
            e
            for e in entries
            if (config.min_file_size == 0 or e.size >= config.min_file_size)
            and (config.max_file_size == 0 or e.size <= config.max_file_size)
            and (config.newer_than is None or (e.mtime_ns / 1e9) >= config.newer_than)
            and (config.older_than is None or (e.mtime_ns / 1e9) <= config.older_than)
        ]
    return entries