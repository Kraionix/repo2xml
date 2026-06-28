# src/repo2xml/contracts/stats.py
from __future__ import annotations

from typing import Protocol


class StatsProvider(Protocol):
    """Protocol for components that provide statistics."""

    def get_stats(self) -> dict[str, object]:
        """Return a dictionary of statistics for this component.

        The returned dictionary may contain any keys; it is up to the
        StatisticsCollector to interpret and merge them into ExportStats.
        """
        ...