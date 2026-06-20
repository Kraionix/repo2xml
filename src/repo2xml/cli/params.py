# src/repo2xml/cli/params.py
"""
CLI parameter helpers (defaults, validators, shared option builders).

These are deliberately kept as simple functions to make the main callback
signature smaller and to allow reuse in future subcommands.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

import typer


def parse_datetime_arg(value: str) -> float:
    """Parse an ISO‑8601 date/time string into UTC epoch seconds."""
    try:
        dt = datetime.fromisoformat(value)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.timestamp()
    except (ValueError, OverflowError) as e:
        raise typer.BadParameter(f"Invalid date/time: {e}")