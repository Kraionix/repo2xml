# src/repo2xml/cli/ui.py
from __future__ import annotations

import logging
from enum import Enum


class LogLevel(str, Enum):
    """Logging verbosity."""
    info = "info"
    warning = "warning"
    error = "error"


def setup_logging(level: LogLevel, *, no_color: bool = False) -> logging.Logger:
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
        from rich.console import Console
        from rich.logging import RichHandler

        console = Console(no_color=no_color)
        logging.basicConfig(
            level=mapping[level],
            format="%(message)s",
            handlers=[RichHandler(console=console, show_time=False, show_level=True, show_path=False)],
        )
    except ImportError:
        # Fallback to plain formatting (e.g., during testing without Rich)
        logging.basicConfig(
            level=mapping[level],
            format="%(levelname)s: %(message)s",
        )

    return logging.getLogger("repo2xml.cli")