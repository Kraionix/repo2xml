# src/repo2xml/application/scanner_service.py
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

from repo2xml.application.contracts import ScannerLike
from repo2xml.application.filters import apply_file_filters
from repo2xml.config import ExportConfig
from repo2xml.domain.model import FileEntry
from repo2xml.services.scan.scanner import ScanStats


@dataclass(slots=True)
class ScanResult:
    """Result of a scan operation."""
    entries: List[FileEntry]
    stats: ScanStats
    warnings: Optional[str] = None


class ScannerService:
    """
    Encapsulates filesystem scanning and filtering.

    Delegates the actual scan to a ScannerLike instance, then applies
    file‑level filters (size, mtime) and collects scanner warnings.
    """

    def __init__(self, scanner: ScannerLike, config: ExportConfig):
        self.scanner = scanner
        self.config = config

    def scan(self, root_path: Path) -> ScanResult:
        """
        Perform the scan, apply filters, and return the result.

        The scanner is expected to yield FileEntry objects.  We materialise
        the entries into a list so that filtering and later structure writing
        can work with a stable collection.
        """
        entries: List[FileEntry] = []
        for entry in self.scanner.scan():
            entries.append(entry)

        entries = apply_file_filters(entries, self.config)

        warnings: Optional[str] = None
        stats = self.scanner.stats
        if stats is not None and stats.has_issues():
            warnings = stats.summary()

        return ScanResult(entries=entries, stats=stats or ScanStats(), warnings=warnings)