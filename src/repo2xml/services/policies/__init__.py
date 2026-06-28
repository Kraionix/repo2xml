# src/repo2xml/services/policies/__init__.py
"""
Policy implementations for file processing.

This package contains concrete FilePolicy implementations used by the
BuildPayloadStep. Each policy handles a specific aspect of file processing
(symlinks, modes, errors, binary, text).
"""

from .symlink_policy import SymlinkPolicy
from .mode_policy import ModePolicy
from .error_policy import ErrorPolicy
from .binary_policy import BinaryPolicy
from .text_policy import TextPolicy

__all__ = [
    "SymlinkPolicy",
    "ModePolicy",
    "ErrorPolicy",
    "BinaryPolicy",
    "TextPolicy",
]