# src/repo2xml/services/scan/__init__.py
"""Scanning subsystem (filesystem traversal + filtering)."""

# Import registry so that built‑in scanners are registered at startup.
from repo2xml.services.scan import registry  # noqa: F401