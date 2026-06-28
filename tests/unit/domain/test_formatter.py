# tests/unit/domain/test_formatter.py
"""Unit tests for ReasonFormatter."""

import pytest

from repo2xml.domain.formatter import ReasonFormatter
from repo2xml.domain.model import ErrorCode, ErrorInfo, SkipCode, SkipInfo


class TestReasonFormatter:
    def test_format_skip_binary_skip_mode(self) -> None:
        info = SkipInfo(code=SkipCode.binary_skip_mode)
        result = ReasonFormatter.format_skip(info)
        assert result == "Skipped: Binary file detected (binary mode: skip)"

    def test_format_skip_text_size_limit(self) -> None:
        info = SkipInfo(code=SkipCode.text_size_limit, detail={"size": 2000, "limit": 1000})
        result = ReasonFormatter.format_skip(info)
        assert result == "Skipped: File size 2000 exceeds text limit 1000"

    def test_format_skip_base64_size_limit(self) -> None:
        info = SkipInfo(code=SkipCode.base64_size_limit, detail={"size": 5000, "limit": 4000})
        result = ReasonFormatter.format_skip(info)
        assert result == "Skipped: File size 5000 exceeds base64 limit 4000"

    def test_format_skip_hash_size_limit(self) -> None:
        info = SkipInfo(code=SkipCode.hash_size_limit, detail={"size": 10000, "limit": 8000})
        result = ReasonFormatter.format_skip(info)
        assert result == "Skipped: File size 10000 exceeds hash limit 8000"

    def test_format_skip_unknown(self) -> None:
        info = SkipInfo(code=SkipCode.unknown)
        result = ReasonFormatter.format_skip(info)
        assert result == "Skipped"

    def test_format_error_sniff_read_error(self) -> None:
        info = ErrorInfo(code=ErrorCode.sniff_read_error, detail={"os_error": "Permission denied"})
        result = ReasonFormatter.format_error(info)
        assert result == "Error reading file sample: Permission denied"

    def test_format_error_stat_error(self) -> None:
        info = ErrorInfo(code=ErrorCode.stat_error, detail={"os_error": "No such file"})
        result = ReasonFormatter.format_error(info)
        assert result == "Error stat file: No such file"

    def test_format_error_text_read_error(self) -> None:
        info = ErrorInfo(code=ErrorCode.text_read_error, detail={"os_error": "I/O error"})
        result = ReasonFormatter.format_error(info)
        assert result == "Error reading file: I/O error"

    def test_format_error_text_decode_error(self) -> None:
        info = ErrorInfo(
            code=ErrorCode.text_decode_error,
            detail={"encoding": "utf-8", "decode_error": "invalid start byte"},
        )
        result = ReasonFormatter.format_error(info)
        assert result == "Error decoding with utf-8: invalid start byte"

    def test_format_error_binary_hash_error(self) -> None:
        info = ErrorInfo(code=ErrorCode.binary_hash_error, detail={"os_error": "Permission denied"})
        result = ReasonFormatter.format_error(info)
        assert result == "Error hashing file: Permission denied"

    def test_format_error_base64_error(self) -> None:
        info = ErrorInfo(code=ErrorCode.base64_error, detail={"os_error": "I/O error"})
        result = ReasonFormatter.format_error(info)
        assert result == "Error base64-encoding file: I/O error"

    def test_format_error_unknown(self) -> None:
        info = ErrorInfo(code=ErrorCode.unknown)
        result = ReasonFormatter.format_error(info)
        assert result == "Error"