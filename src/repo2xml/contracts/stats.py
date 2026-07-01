# src/repo2xml/contracts/stats.py
from __future__ import annotations

from typing import Protocol

from repo2xml.domain.model import ExportStats


class StatsProvider(Protocol):
    """Protocol for components that provide statistics."""

    def apply_to(self, stats: ExportStats) -> None:
        """Apply this provider's statistics to the given ExportStats object.

        Each provider is responsible for updating the relevant fields of
        the ExportStats instance (e.g., redaction_stats, classification_stats,
        scan_stats, etc.).
        """
        ...