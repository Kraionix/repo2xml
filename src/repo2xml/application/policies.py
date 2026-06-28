# src/repo2xml/application/policies.py
from __future__ import annotations

from typing import List, Optional

from repo2xml.contracts import FilePolicy
from repo2xml.domain.model import (
    ClassificationResult,
    ErrorCode,
    ErrorInfo,
    ErrorPayload,
    FileEntry,
    FilePayload,
    SkipCode,
    SkipInfo,
)


class ReasonFormatter:
    """Convert structured error/skip info into human-readable messages."""

    @staticmethod
    def format_skip(info: SkipInfo) -> str:
        code = info.code
        d = info.detail
        if code == SkipCode.binary_skip_mode:
            return "Skipped: Binary file detected (binary mode: skip)"
        if code == SkipCode.text_size_limit:
            size = d.get("size")
            limit = d.get("limit")
            return f"Skipped: File size {size} exceeds text limit {limit}"
        if code == SkipCode.base64_size_limit:
            size = d.get("size")
            limit = d.get("limit")
            return f"Skipped: File size {size} exceeds base64 limit {limit}"
        if code == SkipCode.hash_size_limit:
            size = d.get("size")
            limit = d.get("limit")
            return f"Skipped: File size {size} exceeds hash limit {limit}"
        return "Skipped"

    @staticmethod
    def format_error(info: ErrorInfo) -> str:
        code = info.code
        d = info.detail
        os_error = d.get("os_error")
        if code == ErrorCode.sniff_read_error:
            return f"Error reading file sample: {os_error}"
        if code == ErrorCode.stat_error:
            return f"Error stat file: {os_error}"
        if code == ErrorCode.text_read_error:
            return f"Error reading file: {os_error}"
        if code == ErrorCode.text_decode_error:
            enc = d.get("encoding", "unknown")
            return f"Error decoding with {enc}: {d.get('decode_error')}"
        if code == ErrorCode.binary_detected:
            return "Binary file detected during text read"
        if code == ErrorCode.binary_hash_error:
            return f"Error hashing file: {os_error}"
        if code == ErrorCode.base64_error:
            return f"Error base64-encoding file: {os_error}"
        if code == ErrorCode.processor_error:
            return f"Text processor error: {d.get('processor_error')}"
        return "Error"


class ExportPayloadBuilder:
    """
    Builds a FilePayload for a given file entry by applying a chain of FilePolicy objects.

    The policies are applied in the order they are provided. The first policy
    that returns a non-None payload determines the final outcome. If no policy
    matches, an ErrorPayload is returned as a fallback.

    This class is essentially a coordinator; the actual logic resides in the
    individual policy implementations.
    """

    def __init__(self, policies: List[FilePolicy]) -> None:
        """
        Args:
            policies: Ordered list of FilePolicy instances to apply.
        """
        self._policies = policies

    def build(self, entry: FileEntry, classification: ClassificationResult) -> FilePayload:
        """
        Apply the chain of policies to the given entry and classification.

        Returns:
            The FilePayload produced by the first matching policy, or a fallback
            ErrorPayload if no policy matches.
        """
        for policy in self._policies:
            result = policy.apply(entry, classification)
            if result is not None:
                return result

        # Fallback – should never happen if the policy list is complete.
        return ErrorPayload(
            code=ErrorCode.unknown,
            message="No policy matched for this file",
            detail={"entry": entry.rel_path, "kind": classification.kind},
        )