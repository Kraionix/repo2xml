# src/repo2xml/services/scan/__init__.py
"""Scanning subsystem (filesystem traversal + filtering)."""

from repo2xml.services.scan.scanner import FileSystemScanner, ScanStats

# Import registry so that built‑in scanners are registered at startup.
from repo2xml.services.scan import registry  # noqa: F401

__all__ = ["FileSystemScanner", "ScanStats"]