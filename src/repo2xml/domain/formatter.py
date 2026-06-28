# src/repo2xml/domain/formatter.py
from __future__ import annotations

from repo2xml.domain.model import ErrorCode, ErrorInfo, SkipCode, SkipInfo


class ReasonFormatter:
    """Convert structured error/skip info into human-readable messages."""

    @staticmethod
    def format_skip(info: SkipInfo) -> str:
        code = info.code
        d = info.detail
        if code == SkipCode.binary_skip_mode:
            return "Skipped: Binary file detected (binary mode: skip)"
        if code == SkipCode.text_size_limit:
            size = d.get("size")
            limit = d.get("limit")
            return f"Skipped: File size {size} exceeds text limit {limit}"
        if code == SkipCode.base64_size_limit:
            size = d.get("size")
            limit = d.get("limit")
            return f"Skipped: File size {size} exceeds base64 limit {limit}"
        if code == SkipCode.hash_size_limit:
            size = d.get("size")
            limit = d.get("limit")
            return f"Skipped: File size {size} exceeds hash limit {limit}"
        return "Skipped"

    @staticmethod
    def format_error(info: ErrorInfo) -> str:
        code = info.code
        d = info.detail
        os_error = d.get("os_error")
        if code == ErrorCode.sniff_read_error:
            return f"Error reading file sample: {os_error}"
        if code == ErrorCode.stat_error:
            return f"Error stat file: {os_error}"
        if code == ErrorCode.text_read_error:
            return f"Error reading file: {os_error}"
        if code == ErrorCode.text_decode_error:
            enc = d.get("encoding", "unknown")
            return f"Error decoding with {enc}: {d.get('decode_error')}"
        if code == ErrorCode.binary_detected:
            return "Binary file detected during text read"
        if code == ErrorCode.binary_hash_error:
            return f"Error hashing file: {os_error}"
        if code == ErrorCode.base64_error:
            return f"Error base64-encoding file: {os_error}"
        if code == ErrorCode.processor_error:
            return f"Text processor error: {d.get('processor_error')}"
        return "Error"