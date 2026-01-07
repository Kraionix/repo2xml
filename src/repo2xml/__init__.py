"""
repo2xml - Convert source code repositories into structured XML for LLMs.

Exposes the high-level API and Configuration object for library usage.
"""

from .api import Repo2XML
from .config import Repo2XMLConfig, Mode, BinaryMode, Formatting

__all__ = ["Repo2XML", "Repo2XMLConfig", "Mode", "BinaryMode", "Formatting"]