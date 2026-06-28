# src/repo2xml/services/output/__init__.py
"""Output targets and compression wrappers."""

from repo2xml.services.output.targets import (
    CompressMode,
    open_output_stream,
    OutputTarget,
    FileTarget,
    StdoutTarget,
    ClipboardTarget,
    DevNullTarget,
)

__all__ = [
    "CompressMode",
    "open_output_stream",
    "OutputTarget",
    "FileTarget",
    "StdoutTarget",
    "ClipboardTarget",
    "DevNullTarget",
]