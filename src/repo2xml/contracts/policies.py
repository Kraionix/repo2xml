# src/repo2xml/contracts/policies.py
from __future__ import annotations

from typing import Optional, Protocol

from repo2xml.domain.model import ClassificationResult, FileEntry, FilePayload


class FilePolicy(Protocol):
    """
    Protocol for file processing policies.

    A policy decides how to handle a given file entry based on its metadata
    and classification result. If the policy applies, it returns a FilePayload.
    If it does not apply, it returns None, allowing the next policy in the chain
    to handle the file.
    """

    def apply(self, entry: FileEntry, classification: ClassificationResult) -> Optional[FilePayload]:
        """
        Process the file entry.

        Args:
            entry: The file entry to process.
            classification: The classification result (text/binary/error).

        Returns:
            A FilePayload if this policy applies, otherwise None.
        """
        ...