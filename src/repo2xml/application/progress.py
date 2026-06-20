# src/repo2xml/application/progress.py
from __future__ import annotations

import time
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

    def set_warning_count(self, count: int) -> None:
        return

    def set_postfix(self, text: str) -> None:
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
    Rich-based progress reporter with throttled updates.

    Supports indeterminate phases, phase switching, optional detail,
    warning counts and a per‑file postfix.

    Updates are throttled to ~20 Hz (min interval 0.05 s) to avoid
    overwhelming the terminal with thousands of refresh calls per second
    when processing many small files.
    """

    def __init__(self, *, desc: str = "repo2xml", unit: str = "file"):
        from rich.progress import BarColumn, Progress, TextColumn, TimeRemainingColumn

        self.progress = Progress(
            TextColumn("{task.description}"),
            BarColumn(),
            TextColumn("{task.percentage:>3.0f}%"),
            TimeRemainingColumn(),
            TextColumn("{task.fields[warnings]}", style="yellow"),
            TextColumn("{task.fields[current_file]}", style="dim"),
        )
        self.task_id = self.progress.add_task(
            desc, total=None, warnings="", current_file=""
        )
        self.progress.start()

        # Throttling state
        self._pending_advances = 0
        self._last_flush_time = 0.0
        self._min_interval = 0.05  # seconds

        # Cached field values to avoid redundant updates
        self._displayed_postfix = ""
        self._pending_postfix: Optional[str] = None
        self._displayed_warnings = ""
        self._pending_warnings: Optional[str] = None

    # ------------------------------------------------------------------
    # Public protocol methods
    # ------------------------------------------------------------------

    def set_total(self, total: Optional[int]) -> None:
        self.progress.update(self.task_id, total=total)
        # Reset throttling when the phase changes
        self._pending_advances = 0
        self._last_flush_time = time.time()

    def advance(self, n: int = 1) -> None:
        # Skip updates in indeterminate mode (total is None)
        if self.progress.tasks[self.task_id].total is None:
            return

        self._pending_advances += n
        self._flush_if_needed()

    def set_description(self, desc: str) -> None:
        self.progress.update(self.task_id, description=desc)

    def set_phase(self, phase: str) -> None:
        self.progress.update(self.task_id, description=phase)

    def set_warning_count(self, count: int) -> None:
        text = f"⚠ {count}" if count > 0 else ""
        if text != self._displayed_warnings:
            self._pending_warnings = text

    def set_postfix(self, text: str) -> None:
        if text != self._displayed_postfix:
            self._pending_postfix = text

    def finish(self) -> None:
        self._flush(force=True)
        self.progress.stop()

    # ------------------------------------------------------------------
    # Internal throttling logic
    # ------------------------------------------------------------------

    def _flush_if_needed(self) -> None:
        now = time.time()
        if now - self._last_flush_time >= self._min_interval:
            self._flush(now=now)

    def _flush(self, *, force: bool = False, now: Optional[float] = None) -> None:
        if now is None:
            now = time.time()

        # Nothing to update
        if not force and self._pending_advances == 0 and self._pending_postfix is None and self._pending_warnings is None:
            return

        kwargs: dict = {}
        if self._pending_advances:
            kwargs["advance"] = self._pending_advances
            self._pending_advances = 0

        if self._pending_postfix is not None:
            kwargs["current_file"] = self._pending_postfix
            self._displayed_postfix = self._pending_postfix
            self._pending_postfix = None

        if self._pending_warnings is not None:
            kwargs["warnings"] = self._pending_warnings
            self._displayed_warnings = self._pending_warnings
            self._pending_warnings = None

        self.progress.update(self.task_id, **kwargs)
        self._last_flush_time = now