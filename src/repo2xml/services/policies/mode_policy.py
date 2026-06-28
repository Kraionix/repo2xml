# src/repo2xml/services/policies/mode_policy.py
from __future__ import annotations

from typing import Optional

from repo2xml.contracts import FilePolicy
from repo2xml.config import Mode
from repo2xml.domain.model import (
    ClassificationResult,
    FileEntry,
    FilePayload,
    MetadataPayload,
)


class ModePolicy(FilePolicy):
    """
    Policy for export mode.

    Currently handles only `metadata` mode: returns a MetadataPayload for any file.
    For `full` mode, it returns None (delegates to subsequent policies).
    """

    def __init__(self, mode: Mode) -> None:
        self._mode = mode

    def apply(self, entry: FileEntry, classification: ClassificationResult) -> Optional[FilePayload]:
        if self._mode == Mode.metadata:
            return MetadataPayload()
        return None