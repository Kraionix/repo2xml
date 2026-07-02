# src/repo2xml/application/scanner_service.py
from __future__ import annotations

from pathlib import Path
from typing import List, Optional

from repo2xml.contracts import ScannerLike, ScanUseCase
from repo2xml.application.filters import apply_file_filters
from repo2xml.config import FilterConfig
from repo2xml.domain.model import FileEntry, ScanResult
from repo2xml.services.scan.scanner import ScanStats


class FilesystemScanUseCase(ScanUseCase):
    """
    Filesystem implementation of ScanUseCase.

    Encapsulates filesystem scanning and filtering using a ScannerLike instance.
    """

    def __init__(self, scanner: ScannerLike, filter_config: FilterConfig):
        self.scanner = scanner
        self.filter_config = filter_config

    def execute(self, root_path: Path) -> ScanResult:
        """
        Perform scanning, filtering, and sorting of entries.

        Args:
            root_path: The root directory for the scan (used for logging, not passed to scanner).

        Returns:
            ScanResult with sorted and filtered entries and scanner statistics.
        """
        # Collect all entries from the scanner
        entries: List[FileEntry] = []
        for entry in self.scanner.scan():
            entries.append(entry)

        # Apply filters (size, mtime)
        entries = apply_file_filters(entries, self.filter_config)

        # Sort deterministically by relative path
        entries.sort(key=lambda e: e.rel_path)

        # Collect scanner warnings
        warnings: Optional[str] = None
        stats = self.scanner.stats
        if stats is not None and stats.has_issues():
            warnings = stats.summary()

        return ScanResult(
            entries=entries,
            stats=stats or ScanStats(),
            warnings=warnings,
        )