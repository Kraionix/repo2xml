# src/repo2xml/application/progress.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional, Protocol


class ProgressReporter(Protocol):
    """Progress reporting contract (supports multi-phase progress)."""

    def set_total(self, total: Optional[int]) -> None:
        ...

    def advance(self, n: int = 1) -> None:
        ...

    def finish(self) -> None:
        ...

    def set_description(self, desc: str) -> None:
        ...

    def set_phase(self, phase: str) -> None:
        ...


@dataclass(slots=True)
class NullProgressReporter:
    """No-op progress reporter."""

    def set_total(self, total: Optional[int]) -> None:
        return

    def advance(self, n: int = 1) -> None:
        return

    def finish(self) -> None:
        return

    def set_description(self, desc: str) -> None:
        return

    def set_phase(self, phase: str) -> None:
        return


@dataclass(slots=True)
class CallbackProgressReporter:
    """
    Progress reporter wrapping a simple callback.

    The callback is called with the delta increment (same semantics as tqdm.update()).
    """

    callback: Callable[[int], None]

    def set_total(self, total: Optional[int]) -> None:
        return

    def advance(self, n: int = 1) -> None:
        self.callback(n)

    def finish(self) -> None:
        return

    def set_description(self, desc: str) -> None:
        return

    def set_phase(self, phase: str) -> None:
        return


class RichProgressReporter:
    """
    Rich-based progress reporter.

    Supports indeterminate phases, phase switching, and optional detail.
    Kept in the application layer so future presentation layers can reuse it.
    """

    def __init__(self, *, desc: str = "repo2xml", unit: str = "file"):
        from rich.progress import BarColumn, Progress, TextColumn, TimeRemainingColumn

        self.progress = Progress(
            TextColumn("{task.description}"),
            BarColumn(),
            TextColumn("{task.percentage:>3.0f}%"),
            TimeRemainingColumn(),
        )
        self.task_id = self.progress.add_task(desc, total=None)
        self.progress.start()

    def set_total(self, total: Optional[int]) -> None:
        self.progress.update(self.task_id, total=total)

    def advance(self, n: int = 1) -> None:
        self.progress.update(self.task_id, advance=n)

    def set_description(self, desc: str) -> None:
        # Not natively supported as a postfix; update the description instead.
        self.progress.update(self.task_id, description=desc)

    def set_phase(self, phase: str) -> None:
        self.progress.update(self.task_id, description=phase)

    def finish(self) -> None:
        self.progress.stop()