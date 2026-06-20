# src/repo2xml/cli/ui.py
from __future__ import annotations

import logging
from enum import Enum


class LogLevel(str, Enum):
    """Logging verbosity."""
    info = "info"
    warning = "warning"
    error = "error"


def setup_logging(level: LogLevel) -> logging.Logger:
    """
    Configure stderr logging with Rich handler for colorised output.

    We use Rich's logging handler to present structured, diff-friendly messages.
    The fallback to the standard stream handler is automatic if Rich is unavailable
    (should not happen with our dependency).
    """
    mapping = {
        LogLevel.info: logging.INFO,
        LogLevel.warning: logging.WARNING,
        LogLevel.error: logging.ERROR,
    }
    try:
        from rich.logging import RichHandler

        logging.basicConfig(
            level=mapping[level],
            format="%(message)s",
            handlers=[RichHandler(show_time=False, show_level=True, show_path=False)],
        )
    except ImportError:
        # Fallback to plain formatting (e.g., during testing without Rich)
        logging.basicConfig(
            level=mapping[level],
            format="%(levelname)s: %(message)s",
        )

    return logging.getLogger("repo2xml.cli")