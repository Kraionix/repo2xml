from __future__ import annotations

import gzip
import sys
from enum import Enum
from pathlib import Path
from typing import BinaryIO, Callable, Optional, Tuple


class CompressMode(str, Enum):
    """Output compression for the whole stream."""
    none = "none"
    gzip = "gzip"
    zstd = "zstd"


def try_relpath_posix(child: Path, root: Path) -> Optional[str]:
    """Return POSIX relative path if child is inside root, else None."""
    try:
        return child.resolve().relative_to(root.resolve()).as_posix()
    except Exception:
        return None


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
    """
    if use_stdout:
        base: BinaryIO = sys.stdout.buffer
        if compress == CompressMode.none:
            return base, lambda: None

        if compress == CompressMode.gzip:
            gz = gzip.GzipFile(fileobj=base, mode="wb")
            return gz, gz.close

        if compress == CompressMode.zstd:
            import zstandard as zstd  # type: ignore
            cctx = zstd.ZstdCompressor(level=3)
            zw = cctx.stream_writer(base)
            return zw, zw.close

    # File output
    output_path.parent.mkdir(parents=True, exist_ok=True)
    raw = open(output_path, "wb")

    if compress == CompressMode.none:
        return raw, raw.close

    if compress == CompressMode.gzip:
        gz = gzip.GzipFile(fileobj=raw, mode="wb")
        return gz, lambda: (gz.close(), raw.close())

    if compress == CompressMode.zstd:
        import zstandard as zstd  # type: ignore
        cctx = zstd.ZstdCompressor(level=3)
        zw = cctx.stream_writer(raw)
        return zw, lambda: (zw.close(), raw.close())

    return raw, raw.close