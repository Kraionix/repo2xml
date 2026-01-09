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


class TqdmProgressReporter:
    """
    tqdm-based reporter.

    This is kept in the application layer (not CLI) so future presentation layers
    can also reuse it if needed.
    """

    def __init__(self, *, desc: str = "repo2xml", unit: str = "file"):
        from tqdm import tqdm  # local import keeps import cost optional-ish

        self._tqdm_cls = tqdm
        # Start in indeterminate mode so we can show scanning progress without a total.
        self._bar = self._tqdm_cls(desc=desc, unit=unit, total=None)

    def set_total(self, total: Optional[int]) -> None:
        # tqdm supports total=None for indeterminate progress.
        # We reset the bar when switching phases (e.g., Scanning -> Processing).
        try:
            self._bar.reset(total=total)
        except TypeError:
            # Some tqdm versions accept positional arguments only.
            self._bar.reset(total)

        # Ensure visuals update immediately.
        try:
            self._bar.refresh()
        except Exception:
            pass

    def advance(self, n: int = 1) -> None:
        self._bar.update(n)

    def set_description(self, desc: str) -> None:
        # Postfix is useful for small contextual details.
        try:
            self._bar.set_postfix_str(desc, refresh=True)
        except Exception:
            pass

    def set_phase(self, phase: str) -> None:
        try:
            # set_description_str is available on newer tqdm, fallback to set_description.
            if hasattr(self._bar, "set_description_str"):
                self._bar.set_description_str(phase)
            else:
                self._bar.set_description(phase)
        except Exception:
            pass

    def finish(self) -> None:
        try:
            self._bar.close()
        except Exception:
            pass