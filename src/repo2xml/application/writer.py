from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable


@dataclass(slots=True)
class BufferedTextWriter:
    """
    Simple string write buffer to reduce overhead of many small write() calls.

    This is not a micro-optimization: serializers tend to emit many fragments, and
    batching them reduces Python-level call overhead.

    max_buffer_chars:
      - 0 disables buffering (passthrough).
      - Otherwise, the buffer flushes when reaching this size.
    """
    write_fn: Callable[[str], None]
    flush_fn: Callable[[], None]
    max_buffer_chars: int = 0

    # With slots=True, internal state must be declared explicitly.
    _buf: list[str] = field(default_factory=list, init=False, repr=False)
    _buf_len: int = field(default=0, init=False, repr=False)

    def write(self, s: str) -> None:
        if not s:
            return

        if self.max_buffer_chars <= 0:
            self.write_fn(s)
            return

        self._buf.append(s)
        self._buf_len += len(s)

        if self._buf_len >= self.max_buffer_chars:
            self.flush()

    def flush(self) -> None:
        if self._buf_len == 0:
            return

        self.write_fn("".join(self._buf))
        self._buf.clear()
        self._buf_len = 0

        # Flush underlying stream buffers too.
        self.flush_fn()