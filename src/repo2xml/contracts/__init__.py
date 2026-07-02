# src/repo2xml/contracts/__init__.py
"""
Contracts package.

Design rule for choosing between Protocol and ABC:
- Use Protocol for interfaces with 1-3 methods that do not need shared implementation.
- Use ABC for interfaces with more methods or when implementations are expected to inherit common logic.

Rationale: Protocol enables structural subtyping (flexible, no need to inherit),
while ABC provides explicit hierarchy and potential code reuse.
"""

from .document_writer import DocumentWriter
from .ingest import IngestorLike
from .policies import FilePolicy
from .progress import ProgressReporter
from .scan import IgnoreProvider, ScannerLike, ScanStatsLike
from .scan_usecase import ScanUseCase
from .serialize import Deserializer, FormatFactory
from .stats import StatsProvider
from .tokenize import TokenCounter, TokenCounterFactory

__all__ = [
    "DocumentWriter",
    "IngestorLike",
    "FilePolicy",
    "ProgressReporter",
    "IgnoreProvider",
    "ScannerLike",
    "ScanStatsLike",
    "ScanUseCase",
    "Deserializer",
    "FormatFactory",
    "StatsProvider",
    "TokenCounter",
    "TokenCounterFactory",
]