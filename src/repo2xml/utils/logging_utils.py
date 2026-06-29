"""
Logging utilities, including context managers for temporary logger level changes.
"""
from __future__ import annotations

import contextlib
import logging
from typing import Generator


@contextlib.contextmanager
def temporary_logger_level(logger_name: str, level: int) -> Generator[None, None, None]:
    """
    Temporarily change the log level of a logger.

    The original level is restored after the context block exits.

    Args:
        logger_name: Name of the logger (e.g., "transformers").
        level: Desired log level (e.g., logging.WARNING).
    Yields:
        None
    """
    logger = logging.getLogger(logger_name)
    old_level = logger.level  # Can be 0 (NOTSET) if not explicitly set
    try:
        logger.setLevel(level)
        yield
    finally:
        # Restore previous level. If old_level was NOTSET, this reverts to
        # inheriting from parent loggers.
        logger.setLevel(old_level)