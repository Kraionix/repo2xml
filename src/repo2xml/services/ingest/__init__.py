# src/repo2xml/services/ingest/__init__.py
"""Ingestion subsystem (safe content reading + classification + redaction)."""

from repo2xml.services.ingest.redact import RedactionEngine, RedactionStats
from repo2xml.services.ingest.ingestor import StandardIngestor

__all__ = ["RedactionEngine", "RedactionStats", "StandardIngestor"]