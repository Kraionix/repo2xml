# src/repo2xml/services/ingest/ingestor.py
from __future__ import annotations

import base64
import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional

from repo2xml.domain.model import ErrorCode, ErrorInfo, SkipCode, SkipInfo, TextReadResult

_DEFAULT_CHUNK_SIZE = 64 * 1024


class StandardIngestor:
    """Responsible for reading file contents after classification."""

    def __init__(
        self,
        *,
        newline_mode: str,
        decode_errors: str = "replace",
    ):
        self.newline_mode = newline_mode
        self.decode_errors = decode_errors

    def read_text(
        self,
        path: Path,
        *,
        max_size: int,
        sniff_sample: Optional[bytes] = None,
    ) -> TextReadResult:
        """
        Read and decode a file that has already been classified as text.

        If *sniff_sample* is provided, it is used as the first bytes of the
        file, avoiding a redundant disk read.
        """
        try:
            st = path.stat()
        except OSError as e:
            err = ErrorInfo(code=ErrorCode.stat_error, detail={"os_error": str(e)})
            return TextReadResult(kind="error", error=err)

        if st.st_size > max_size:
            info = SkipInfo(code=SkipCode.text_size_limit, detail={"size": st.st_size, "limit": max_size})
            return TextReadResult(kind="skip", skipped=info)

        try:
            with open(path, "rb") as f:
                if sniff_sample is not None:
                    # The classification already read the first SNIFF_BYTES
                    sample = sniff_sample
                    rest = f.read()
                else:
                    sample = f.read(4096)
                    rest = f.read()
        except OSError as e:
            err = ErrorInfo(code=ErrorCode.text_read_error, detail={"os_error": str(e)})
            return TextReadResult(kind="error", error=err)

        buf = bytearray(sample)
        buf.extend(rest)
        enc = "utf-8"  # encoding hint already provided by classifier
        try:
            if self.decode_errors == "strict":
                text = buf.decode(enc, errors="strict")
            else:
                text = buf.decode(enc, errors="replace")
        except UnicodeDecodeError as e:
            err = ErrorInfo(code=ErrorCode.text_decode_error, detail={"encoding": enc, "decode_error": str(e)})
            return TextReadResult(kind="error", error=err)
        except Exception as e:
            err = ErrorInfo(code=ErrorCode.text_decode_error, detail={"encoding": enc, "decode_error": str(e)})
            return TextReadResult(kind="error", error=err)

        if self.newline_mode == "lf":
            text = text.replace("\r\n", "\n").replace("\r", "\n")
        return TextReadResult(kind="text", text=text, encoding=enc)

    @staticmethod
    def sha256_file(path: Path, *, chunk_size: int = _DEFAULT_CHUNK_SIZE) -> str:
        h = hashlib.sha256()
        with open(path, "rb") as f:
            while True:
                chunk = f.read(chunk_size)
                if not chunk:
                    break
                h.update(chunk)
        return h.hexdigest()

    @staticmethod
    def iter_base64_chunks(path: Path, *, chunk_size: int = _DEFAULT_CHUNK_SIZE) -> Iterable[str]:
        rem = b""
        with open(path, "rb") as f:
            while True:
                chunk = f.read(chunk_size)
                if not chunk:
                    break
                data = rem + chunk
                n = (len(data) // 3) * 3
                block = data[:n]
                rem = data[n:]
                if block:
                    yield base64.b64encode(block).decode("ascii")
        if rem:
            yield base64.b64encode(rem).decode("ascii")