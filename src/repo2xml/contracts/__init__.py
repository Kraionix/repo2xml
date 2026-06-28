# src/repo2xml/contracts/__init__.py
"""
Public contracts (protocols and abstract base classes) used across layers.

This package contains all interfaces that define the behaviour of
pluggable components. It is imported by both services and application
layers, ensuring that dependencies point inward.
"""

from .scan import ScannerLike, ScanStatsLike, IgnoreProvider
from .ingest import IngestorLike
from .serialize import (
    DocumentMetadataWriter,
    StructureWriter,
    FileSectionWriter,
    FileContentWriter,
    Deserializer,
    FormatFactory,
)
from .tokenize import TokenCounter, TokenCounterFactory
from .progress import ProgressReporter
from .stats import StatsProvider

# FilePolicy has been removed in favour of the pipeline architecture.

__all__ = [
    "ScannerLike",
    "ScanStatsLike",
    "IgnoreProvider",
    "IngestorLike",
    "DocumentMetadataWriter",
    "StructureWriter",
    "FileSectionWriter",
    "FileContentWriter",
    "Deserializer",
    "FormatFactory",
    "TokenCounter",
    "TokenCounterFactory",
    "ProgressReporter",
    "StatsProvider",
]