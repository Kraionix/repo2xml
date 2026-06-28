# src/repo2xml/contracts/tokenize.py
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Protocol

from repo2xml.domain.model import TokenStats


class TokenCounter(Protocol):
    """Protocol for token counters."""

    def count(self, text: str, ext: str = "") -> int:
        """Count tokens in text, updating internal stats. Return token count."""
        ...

    def get_stats(self) -> TokenStats:
        """Return accumulated token statistics."""
        ...


class TokenCounterFactory(ABC):
    """Abstract factory for token counters."""

    @abstractmethod
    def create(self, model: str, **kwargs) -> TokenCounter:
        """Create a TokenCounter instance for the given model."""
        ...