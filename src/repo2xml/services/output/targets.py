from __future__ import annotations

import gzip
import io
import os
import sys
from abc import ABC, abstractmethod
from contextlib import contextmanager
from enum import Enum
from pathlib import Path
from typing import BinaryIO, Callable, ContextManager, Generator, Tuple

from repo2xml.domain.exceptions import OutputError
from repo2xml.utils.paths import try_relpath_posix


class CompressMode(str, Enum):
    """Output compression for the whole stream."""
    none = "none"
    gzip = "gzip"
    zstd = "zstd"


def open_output_stream(
    *,
    output_path: Path,
    use_stdout: bool,
    compress: CompressMode,
) -> Tuple[BinaryIO, Callable[[], None]]:
    """
    Open an output stream for the document bytes.
    Handles File vs Stdout and Compression transparently.

    Returns: (binary_stream, closer_callback)

    Raises:
        OutputError: On missing compression dependencies or filesystem errors.
    """
    if use_stdout:
        base: BinaryIO = sys.stdout.buffer
        if compress == CompressMode.none:
            return base, lambda: None

        if compress == CompressMode.gzip:
            gz = gzip.GzipFile(fileobj=base, mode="wb")
            return gz, gz.close

        if compress == CompressMode.zstd:
            try:
                import zstandard as zstd  # type: ignore
            except ImportError as e:
                raise OutputError("zstd compression requires: pip install zstandard") from e

            cctx = zstd.ZstdCompressor(level=3)
            zw = cctx.stream_writer(base)
            return zw, zw.close

        raise OutputError(f"Unknown compression mode: {compress!r}")

    # File output
    try:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        raw = open(output_path, "wb")
    except OSError as e:
        raise OutputError(f"Cannot open output file: {output_path} ({e})") from e

    if compress == CompressMode.none:
        return raw, raw.close

    if compress == CompressMode.gzip:
        gz = gzip.GzipFile(fileobj=raw, mode="wb")
        return gz, lambda: (gz.close(), raw.close())

    if compress == CompressMode.zstd:
        try:
            import zstandard as zstd  # type: ignore
        except ImportError as e:
            try:
                raw.close()
            except Exception:
                pass
            raise OutputError("zstd compression requires: pip install zstandard") from e

        cctx = zstd.ZstdCompressor(level=3)
        zw = cctx.stream_writer(raw)
        return zw, lambda: (zw.close(), raw.close())

    try:
        raw.close()
    except Exception:
        pass
    raise OutputError(f"Unknown compression mode: {compress!r}")


class OutputTarget(ABC):
    """Abstract output target."""

    @abstractmethod
    def open(self) -> ContextManager[BinaryIO]:
        """Return a context manager yielding a writable binary stream."""
        raise NotImplementedError

    @abstractmethod
    def describe(self) -> str:
        """Human-readable description of the target."""
        raise NotImplementedError


class FileTarget(OutputTarget):
    def __init__(self, path: Path, *, compress: CompressMode = CompressMode.none):
        self.path = path
        self.compress = compress

    @contextmanager
    def open(self) -> Generator[BinaryIO, None, None]:
        stream, closer = open_output_stream(
            output_path=self.path,
            use_stdout=False,
            compress=self.compress,
        )
        try:
            yield stream
        finally:
            try:
                closer()
            except Exception:
                pass

    def describe(self) -> str:
        return f"file://{self.path}"


class StdoutTarget(OutputTarget):
    def __init__(self, *, compress: CompressMode = CompressMode.none):
        self.compress = compress

    @contextmanager
    def open(self) -> Generator[BinaryIO, None, None]:
        stream, closer = open_output_stream(
            output_path=Path(os.devnull),  # unused for stdout
            use_stdout=True,
            compress=self.compress,
        )
        try:
            yield stream
        finally:
            try:
                closer()
            except Exception:
                pass

    def describe(self) -> str:
        return "stdout"


class ClipboardTarget(OutputTarget):
    """
    Clipboard output target.

    This target buffers the full output in memory, then copies it to the clipboard.
    """

    @contextmanager
    def open(self) -> Generator[BinaryIO, None, None]:
        buf = io.BytesIO()
        try:
            yield buf
            buf.seek(0)
            try:
                import pyperclip
            except ImportError as e:
                raise OutputError("Clipboard support requires: pip install pyperclip") from e

            try:
                pyperclip.copy(buf.read().decode("utf-8"))
            except pyperclip.PyperclipException as e:
                raise OutputError(f"Clipboard error: {e}") from e
        finally:
            try:
                buf.close()
            except Exception:
                pass

    def describe(self) -> str:
        return "clipboard"


class DevNullTarget(OutputTarget):
    """Discard all output bytes (useful for --stats-only)."""

    @contextmanager
    def open(self) -> Generator[BinaryIO, None, None]:
        try:
            f = open(os.devnull, "wb")
        except OSError as e:
            raise OutputError(f"Cannot open {os.devnull} for writing: {e}") from e

        try:
            yield f
        finally:
            try:
                f.close()
            except Exception:
                pass

    def describe(self) -> str:
        return f"file://{os.devnull}"


__all__ = [
    "CompressMode",
    "open_output_stream",
    "OutputTarget",
    "FileTarget",
    "StdoutTarget",
    "ClipboardTarget",
    "DevNullTarget",
    "try_relpath_posix",
]