# src/repo2xml/application/process_result.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from repo2xml.domain.model import FilePayload, SkipCode, ErrorCode


@dataclass(slots=True)
class ProcessResult:
    """
    Result of processing a single FileEntry.

    Attributes:
        status: One of 'success', 'skipped', 'error'.
        payload: The FilePayload if status is 'success', else None.
        token_count: Number of tokens counted (if enabled and successful), else None.
        skip_code: A code explaining why the file was skipped (if status is 'skipped').
        error_code: A code explaining why the file failed (if status is 'error').
        message: A human-readable message for logging or debugging.
    """

    status: str  # 'success', 'skipped', 'error'
    payload: Optional[FilePayload] = None
    token_count: Optional[int] = None
    skip_code: Optional[SkipCode] = None
    error_code: Optional[ErrorCode] = None
    message: Optional[str] = None

    def __post_init__(self) -> None:
        # Ensure consistency between status and other fields
        if self.status == "success":
            if self.payload is None:
                raise ValueError("ProcessResult with status='success' must have a payload")
            if self.skip_code is not None or self.error_code is not None:
                raise ValueError("ProcessResult with status='success' must not have skip_code or error_code")
        elif self.status == "skipped":
            if self.payload is not None:
                raise ValueError("ProcessResult with status='skipped' must not have a payload")
            if self.skip_code is None:
                raise ValueError("ProcessResult with status='skipped' must have a skip_code")
        elif self.status == "error":
            if self.payload is not None:
                raise ValueError("ProcessResult with status='error' must not have a payload")
            if self.error_code is None:
                raise ValueError("ProcessResult with status='error' must have an error_code")
        else:
            raise ValueError(f"Invalid status: {self.status!r}")