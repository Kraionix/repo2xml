# src/repo2xml/services/ingest/__init__.py
"""Ingestion subsystem (safe content reading + classification + redaction)."""

from repo2xml.services.ingest.redact_engine import RedactionEngine
from repo2xml.services.ingest.builtin_rules import RedactRule

__all__ = ["RedactionEngine", "RedactRule"]