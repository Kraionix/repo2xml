# src/repo2xml/contracts/scan_usecase.py
from __future__ import annotations

from pathlib import Path
from typing import Protocol

from repo2xml.domain.model import ScanResult


class ScanUseCase(Protocol):
    """Protocol for executing a scan operation and returning filtered results."""

    def execute(self, root_path: Path) -> ScanResult:
        """
        Perform scanning and filtering, return the result.

        Args:
            root_path: The root directory or reference point for the scan.

        Returns:
            ScanResult containing the list of FileEntry objects and metadata.
        """
        ...