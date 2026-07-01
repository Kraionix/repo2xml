# src/repo2xml/services/classify/__init__.py
"""Classification subsystem – determines whether a file is text or binary."""

from repo2xml.domain.model import ClassificationResult, ClassificationStats
from repo2xml.services.classify.engine import ClassificationEngine

__all__ = ["ClassificationEngine", "ClassificationResult", "ClassificationStats"]