# src/repo2xml/services/ingest/redact/models.py
"""Data models for redaction rules and statistics."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List


@dataclass(slots=True)
class Rule:
    """A single redaction rule."""
    name: str
    pattern: str
    replacement: str          # May contain backreferences like \1
    groups: List[str] = field(default_factory=list)
    enabled: bool = True


@dataclass
class RedactionStats:
    """Aggregated statistics collected during redaction."""
    total_files_processed: int = 0
    total_files_skipped: int = 0
    total_matches: int = 0
    matches_by_rule: Dict[str, int] = field(default_factory=dict)