# src/repo2xml/services/ingest/classify/__init__.py
"""Classification subsystem – determines whether a file is text or binary."""

from repo2xml.services.ingest.classify.engine import ClassificationEngine
from repo2xml.services.ingest.classify.models import ClassificationResult, ClassificationStats

__all__ = ["ClassificationEngine", "ClassificationResult", "ClassificationStats"]