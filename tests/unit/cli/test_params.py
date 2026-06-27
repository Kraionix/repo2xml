# tests/unit/cli/test_params.py
"""Unit tests for CLI parameter helpers."""

from datetime import datetime, timedelta, timezone

import pytest
import typer

from repo2xml.cli.params import parse_datetime_arg


class TestParseDatetimeArg:
    def test_valid_iso_with_timezone(self) -> None:
        ts = parse_datetime_arg("2025-01-01T00:00:00+00:00")
        expected = datetime(2025, 1, 1, tzinfo=timezone.utc).timestamp()
        assert ts == expected

    def test_valid_iso_without_timezone(self) -> None:
        ts = parse_datetime_arg("2025-01-01T00:00:00")
        expected = datetime(2025, 1, 1, tzinfo=timezone.utc).timestamp()
        assert ts == expected

    def test_valid_iso_with_timezone_offset(self) -> None:
        ts = parse_datetime_arg("2025-01-01T00:00:00+02:00")
        expected = datetime(2025, 1, 1, tzinfo=timezone(timedelta(hours=2))).timestamp()
        assert ts == expected

    def test_invalid_format_raises_bad_parameter(self) -> None:
        with pytest.raises(typer.BadParameter) as exc_info:
            parse_datetime_arg("not-a-date")
        assert "Invalid date/time" in str(exc_info.value)

    def test_empty_string(self) -> None:
        with pytest.raises(typer.BadParameter):
            parse_datetime_arg("")

    def test_overflow(self) -> None:
        with pytest.raises(typer.BadParameter):
            parse_datetime_arg("9999-99-99T00:00:00")