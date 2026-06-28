# src/repo2xml/services/policies/error_policy.py
from __future__ import annotations

from typing import Optional

from repo2xml.contracts import FilePolicy
from repo2xml.domain.formatter import ReasonFormatter
from repo2xml.domain.model import (
    ClassificationResult,
    ErrorCode,
    ErrorInfo,
    ErrorPayload,
    FileEntry,
    FilePayload,
)


class ErrorPolicy(FilePolicy):
    """
    Policy for handling classification errors.

    If the classification result indicates an error (e.g., failed to read the file),
    this policy returns an ErrorPayload with the appropriate message.
    """

    def apply(self, entry: FileEntry, classification: ClassificationResult) -> Optional[FilePayload]:
        if classification.kind != "error":
            return None

        err = ErrorInfo(
            code=ErrorCode.sniff_read_error,
            detail={"os_error": classification.error or "unknown"},
        )
        return ErrorPayload(
            code=err.code,
            message=ReasonFormatter.format_error(err),
            detail=err.detail,
        )