# src/repo2xml/contracts/progress.py
from __future__ import annotations

from typing import Optional, Protocol


class ProgressReporter(Protocol):
    """Progress reporting contract (supports multi‑phase progress)."""

    def set_total(self, total: Optional[int]) -> None:
        """Set the total number of items (None for indeterminate)."""
        ...

    def advance(self, n: int = 1) -> None:
        """Advance progress by n steps."""
        ...

    def finish(self) -> None:
        """Mark progress as complete."""
        ...

    def set_description(self, desc: str) -> None:
        """Update the description shown to the user."""
        ...

    def set_phase(self, phase: str) -> None:
        """Set the current phase (e.g., 'Scanning', 'Processing')."""
        ...

    def set_warning_count(self, count: int) -> None:
        """Optionally display accumulated warning count."""
        ...

    def set_postfix(self, text: str) -> None:
        """Display extra information (e.g., current file name)."""
        ...