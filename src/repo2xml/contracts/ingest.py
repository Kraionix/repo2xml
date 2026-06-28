# src/repo2xml/contracts/ingest.py
from __future__ import annotations

from pathlib import Path
from typing import Iterable, Optional, Protocol

from repo2xml.domain.model import TextReadResult


class IngestorLike(Protocol):
    """Protocol for reading file contents after classification."""

    def read_text(
        self,
        path: Path,
        *,
        max_size: int,
        sniff_sample: Optional[bytes] = None,
    ) -> TextReadResult:
        """Read and decode a text file, respecting size limits."""
        ...

    def sha256_file(self, path: Path, *, chunk_size: int = 64 * 1024) -> str:
        """Return the SHA‑256 hash of a file."""
        ...

    def iter_base64_chunks(self, path: Path, *, chunk_size: int = 64 * 1024) -> Iterable[str]:
        """Yield base64‑encoded chunks of a binary file."""
        ...