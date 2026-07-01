# src/repo2xml/application/partition/__init__.py
"""
Partitioning subsystem for splitting export output into multiple parts.

This package provides:
- BufferManager: manages buffering of file entries and token counting.
- Partition decision strategies (e.g., TokenBasedStrategy).
- MultiStreamManager: coordinates multiple output streams and handles part switching.
"""

from .buffer_manager import BufferManager
from .decision_strategy import IPartitionDecisionStrategy, TokenBasedStrategy
from .multi_stream_manager import MultiStreamManager

__all__ = [
    "BufferManager",
    "IPartitionDecisionStrategy",
    "TokenBasedStrategy",
    "MultiStreamManager",
]