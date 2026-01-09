"""
repo2xml - Convert source code repositories into a structured context document for LLMs.

Public API:
- Repo2XML: high-level facade for library usage
- Repo2XMLConfig and enums: configuration primitives
"""

from .facade import Repo2XML
from .config import Repo2XMLConfig, Mode, BinaryMode, Formatting, RootPathMode, NewlineMode, SymlinkFilesMode

__all__ = [
    "Repo2XML",
    "Repo2XMLConfig",
    "Mode",
    "BinaryMode",
    "Formatting",
    "RootPathMode",
    "NewlineMode",
    "SymlinkFilesMode",
]