from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional, Protocol


class ProgressReporter(Protocol):
    """Progress reporting contract."""

    def set_total(self, total: int) -> None:
        ...

    def advance(self, n: int = 1) -> None:
        ...

    def finish(self) -> None:
        ...


@dataclass(slots=True)
class NullProgressReporter:
    """No-op progress reporter."""

    def set_total(self, total: int) -> None:
        return

    def advance(self, n: int = 1) -> None:
        return

    def finish(self) -> None:
        return


@dataclass(slots=True)
class CallbackProgressReporter:
    """
    Progress reporter wrapping a simple callback.

    The callback is called with the delta increment (same semantics as tqdm.update()).
    """
    callback: Callable[[int], None]

    def set_total(self, total: int) -> None:
        return

    def advance(self, n: int = 1) -> None:
        self.callback(n)

    def finish(self) -> None:
        return


class TqdmProgressReporter:
    """
    tqdm-based reporter.

    This is kept in the application layer (not CLI) so future presentation layers
    can also reuse it if needed.
    """

    def __init__(self, *, desc: str = "Processing", unit: str = "file"):
        from tqdm import tqdm  # local import keeps import cost optional-ish

        self._tqdm_cls = tqdm
        self._bar = self._tqdm_cls(desc=desc, unit=unit, total=0)

    def set_total(self, total: int) -> None:
        # tqdm allows updating total dynamically.
        self._bar.total = total
        self._bar.refresh()

    def advance(self, n: int = 1) -> None:
        self._bar.update(n)

    def finish(self) -> None:
        try:
            self._bar.close()
        except Exception:
            pass