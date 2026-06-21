# src/repo2xml/services/ingest/__init__.py
"""Ingestion subsystem (reading, classification, redaction)."""

from repo2xml.services.ingest.classify import ClassificationEngine, ClassificationResult, ClassificationStats
from repo2xml.services.ingest.redact import RedactionEngine, RedactionStats
from repo2xml.services.ingest.ingestor import StandardIngestor

__all__ = [
    "ClassificationEngine",
    "ClassificationResult",
    "ClassificationStats",
    "RedactionEngine",
    "RedactionStats",
    "StandardIngestor",
]