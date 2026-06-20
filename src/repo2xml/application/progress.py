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

    def set_warning_count(self, count: int) -> None:
        """Optionally display accumulated warning count."""
        # Default no-op implementation for reporters that don't support it.
        return

    def set_postfix(self, text: str) -> None:
        """Optionally display extra information (e.g., current file)."""
        return


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

    def set_warning_count(self, count: int) -> None:
        return

    def set_postfix(self, text: str) -> None:
        return


class RichProgressReporter:
    """
    Rich-based progress reporter with throttled updates.

    Supports two distinct visual modes:
    - Indeterminate (total=None): spinner with description and optional warnings.
    - Determinate (total>0): bar, percentage, time remaining, current file, warnings.

    Updates in determinate mode are throttled to ~20 Hz (min interval 0.05 s)
    to avoid terminal congestion.
    """

    def __init__(self, *, desc: str = "repo2xml", unit: str = "file", no_color: bool = False):
        from rich.console import Console

        self.console = Console(no_color=no_color)
        self.desc = desc
        self.unit = unit

        self._active_progress = None
        self._active_task_id = None
        self._total: Optional[int] = None

        # Throttling state (shared across phases)
        self._pending_advances = 0
        self._last_flush_time = 0.0
        self._min_interval = 0.05  # seconds

        self._displayed_postfix = ""
        self._pending_postfix: Optional[str] = None
        self._displayed_warnings = ""
        self._pending_warnings: Optional[str] = None

    # ------------------------------------------------------------------
    # Internal helpers for starting the appropriate progress bar
    # ------------------------------------------------------------------

    def _start_indefinite(self) -> None:
        if self._active_progress is not None:
            self._active_progress.stop()
        from rich.progress import Progress, SpinnerColumn, TextColumn

        self._active_progress = Progress(
            SpinnerColumn(),
            TextColumn("{task.description}"),
            TextColumn("{task.fields[warnings]}", style="yellow"),
            console=self.console,
        )
        self._active_task_id = self._active_progress.add_task(
            self.desc, total=None, warnings=""
        )
        self._active_progress.start()

    def _start_definite(self, total: int) -> None:
        if self._active_progress is not None:
            self._active_progress.stop()
        from rich.progress import BarColumn, Progress, TextColumn, TimeRemainingColumn

        self._active_progress = Progress(
            TextColumn("{task.description}"),
            BarColumn(),
            TextColumn("{task.percentage:>3.0f}%"),
            TimeRemainingColumn(),
            TextColumn("{task.fields[warnings]}", style="yellow"),
            TextColumn("{task.fields[current_file]}", style="dim"),
            console=self.console,
        )
        self._active_task_id = self._active_progress.add_task(
            self.desc, total=total, warnings="", current_file=""
        )
        self._active_progress.start()

    # ------------------------------------------------------------------
    # Public protocol methods
    # ------------------------------------------------------------------

    def set_total(self, total: Optional[int]) -> None:
        if total is None:
            if self._active_progress is None or self._total is not None:
                self._start_indefinite()
        else:
            if self._active_progress is None or self._total is None:
                self._start_definite(total)
            else:
                # Already in determinate mode, just update the total.
                self._active_progress.update(self._active_task_id, total=total)
        self._total = total
        self._pending_advances = 0
        self._last_flush_time = time.time()

    def advance(self, n: int = 1) -> None:
        if self._active_progress is None:
            return
        if self._total is None:
            # In indeterminate mode we only keep the spinner alive by
            # refreshing the display on each call (no progress concept).
            self._active_progress.update(self._active_task_id)
            return
        self._pending_advances += n
        self._flush_if_needed()

    def set_description(self, desc: str) -> None:
        self.desc = desc
        if self._active_progress is not None:
            self._active_progress.update(self._active_task_id, description=desc)

    def set_phase(self, phase: str) -> None:
        self.set_description(phase)

    def set_warning_count(self, count: int) -> None:
        text = f"⚠ {count}" if count > 0 else ""
        if text != self._displayed_warnings:
            self._pending_warnings = text

    def set_postfix(self, text: str) -> None:
        if text != self._displayed_postfix:
            self._pending_postfix = text

    def finish(self) -> None:
        self._flush(force=True)
        if self._active_progress is not None:
            self._active_progress.stop()
            self._active_progress = None

    # ------------------------------------------------------------------
    # Internal throttling logic
    # ------------------------------------------------------------------

    def _flush_if_needed(self) -> None:
        now = time.time()
        if now - self._last_flush_time >= self._min_interval:
            self._flush(now=now)

    def _flush(self, *, force: bool = False, now: Optional[float] = None) -> None:
        if self._active_progress is None:
            return
        if now is None:
            now = time.time()
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
        self._active_progress.update(self._active_task_id, **kwargs)
        self._last_flush_time = now