# src/repo2xml/services/ingest/classify/models.py
"""Data models for classification results and statistics."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Literal, Optional


@dataclass(slots=True)
class ClassificationResult:
    """Result of classifying a file."""
    kind: Literal["text", "binary", "error"]
    encoding: Optional[str] = None       # detected encoding (BOM-based)
    sample: Optional[bytes] = None       # first bytes read during analysis
    error: Optional[str] = None          # OS error message if kind == "error"


@dataclass
class ClassificationStats:
    """Aggregated statistics about classification operations."""
    total_files: int = 0
    by_extension: int = 0
    by_content: int = 0
    errors: int = 0