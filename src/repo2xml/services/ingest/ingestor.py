# src/repo2xml/services/ingest/ingestor.py (обновлённый)
from __future__ import annotations

import base64
import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional, Sequence

from repo2xml.domain.model import ErrorCode, ErrorInfo, SkipCode, SkipInfo, SniffResult, TextReadResult
from repo2xml.services.ingest.heuristics import SNIFF_BYTES, detect_bom, looks_binary
from repo2xml.services.ingest.matcher import BinaryExtensionMatcher

_DEFAULT_CHUNK_SIZE = 64 * 1024


class StandardIngestor:
    def __init__(
        self,
        *,
        newline_mode: str,
        decode_errors: str = "replace",
        use_ext_fastpath: bool = True,
        binary_ext_add: Optional[Sequence[str]] = None,
        binary_ext_remove: Optional[Sequence[str]] = None,
    ):
        self.newline_mode = newline_mode
        self.decode_errors = decode_errors
        self.use_ext_fastpath = use_ext_fastpath
        self._ext_matcher: Optional[BinaryExtensionMatcher] = None
        if self.use_ext_fastpath:
            self._ext_matcher = BinaryExtensionMatcher.create(
                add=binary_ext_add,
                remove=binary_ext_remove,
            )

    def sniff(self, path: Path) -> SniffResult:
        if self._ext_matcher is not None and self._ext_matcher.matches(path):
            return SniffResult(kind="binary")
        try:
            with open(path, "rb") as f:
                sample = f.read(SNIFF_BYTES)
        except OSError as e:
            err = ErrorInfo(code=ErrorCode.sniff_read_error, detail={"os_error": str(e)})
            return SniffResult(kind="error", error=err)
        bom_enc = detect_bom(sample)
        if looks_binary(sample, bom_enc):
            return SniffResult(kind="binary", encoding=bom_enc)
        return SniffResult(kind="text", encoding=bom_enc or "utf-8")

    def read_text(self, path: Path, *, max_size: int) -> TextReadResult:
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
                sample = f.read(SNIFF_BYTES)
                bom_enc = detect_bom(sample)
                if looks_binary(sample, bom_enc):
                    err = ErrorInfo(code=ErrorCode.binary_detected, detail={})
                    return TextReadResult(kind="error", error=err)
                rest = f.read()
        except OSError as e:
            err = ErrorInfo(code=ErrorCode.text_read_error, detail={"os_error": str(e)})
            return TextReadResult(kind="error", error=err)
        buf = bytearray(sample)
        buf.extend(rest)
        enc = bom_enc or "utf-8"
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