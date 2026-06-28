# src/repo2xml/services/policies/symlink_policy.py
from __future__ import annotations

from typing import Optional

from repo2xml.contracts import FilePolicy
from repo2xml.config import SymlinkFilesMode
from repo2xml.domain.model import (
    ClassificationResult,
    FileEntry,
    FilePayload,
    LinkPayload,
    SkipCode,
    SkipInfo,
    SkippedPayload,
)
from repo2xml.application.policies import ReasonFormatter


class SymlinkPolicy(FilePolicy):
    """
    Policy for handling symbolic links.

    Depending on the symlink_files mode:
    - `as-link`: returns a LinkPayload (preserves symlink info).
    - `skip`: returns a SkippedPayload.
    - `follow`: returns None (delegates to subsequent policies).
    """

    def __init__(self, mode: SymlinkFilesMode) -> None:
        self._mode = mode

    def apply(self, entry: FileEntry, classification: ClassificationResult) -> Optional[FilePayload]:
        if not entry.is_symlink:
            return None

        if self._mode == SymlinkFilesMode.as_link:
            return LinkPayload(link_target=entry.symlink_target)

        if self._mode == SymlinkFilesMode.skip:
            # Use a generic skip code; detail explains reason
            info = SkipInfo(code=SkipCode.unknown, detail={"reason": "symlink_files_mode=skip"})
            return SkippedPayload(
                code=info.code,
                message=ReasonFormatter.format_skip(info),
                detail=info.detail,
            )

        # follow: no special handling, continue chain
        return None