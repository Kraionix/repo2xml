from __future__ import annotations

import logging
import sys
from enum import Enum

class LogLevel(str, Enum):
    """Logging verbosity."""
    info = "info"
    warning = "warning"
    error = "error"


def setup_logging(level: LogLevel) -> logging.Logger:
    """
    Configure stderr logging.

    We use Python's built-in logging (no extra dependencies). The CLI option
    controls the global level.
    """
    mapping = {
        LogLevel.info: logging.INFO,
        LogLevel.warning: logging.WARNING,
        LogLevel.error: logging.ERROR,
    }
    logging.basicConfig(
        level=mapping[level],
        format="%(levelname)s: %(message)s",
        stream=sys.stderr,
    )
    return logging.getLogger("repo2xml.cli")