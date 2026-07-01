# src/repo2xml/contracts/tokenize.py
from __future__ import annotations

from typing import Protocol

from repo2xml.domain.model import TokenStats, ExportStats


class TokenCounter(Protocol):
    """Protocol for token counters."""

    def count(self, text: str, ext: str = "") -> int:
        """Count tokens in text, updating internal stats. Return token count."""
        ...

    def apply_to(self, stats: ExportStats) -> None:
        """Apply accumulated token statistics to ExportStats."""
        ...


class TokenCounterFactory(Protocol):
    """Abstract factory for token counters."""

    def create(self, model: str, **kwargs) -> TokenCounter:
        """Create a TokenCounter instance for the given model."""
        ...