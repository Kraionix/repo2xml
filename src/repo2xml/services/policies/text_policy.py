# src/repo2xml/services/policies/text_policy.py
from __future__ import annotations

import logging
from typing import Optional

from repo2xml.contracts import FilePolicy, IngestorLike
from repo2xml.config import TextHandlingConfig
from repo2xml.domain.formatter import ReasonFormatter
from repo2xml.domain.model import (
    ClassificationResult,
    ErrorInfo,
    ErrorPayload,
    FileEntry,
    FilePayload,
    SkipCode,
    SkipInfo,
    SkippedPayload,
    TextPayload,
)

logger = logging.getLogger("repo2xml.text_policy")


class TextPolicy(FilePolicy):
    """
    Policy for handling text files.

    Reads the file content using the ingestor, respecting size limits and
    encoding settings. Returns a TextPayload on success, or a SkippedPayload /
    ErrorPayload on failure.
    """

    def __init__(self, config: TextHandlingConfig, ingestor: IngestorLike) -> None:
        self._config = config
        self._ingestor = ingestor

    def apply(self, entry: FileEntry, classification: ClassificationResult) -> Optional[FilePayload]:
        if classification.kind != "text":
            return None

        # Check size limit
        if entry.size > self._config.max_text_size:
            info = SkipInfo(
                code=SkipCode.text_size_limit,
                detail={"size": entry.size, "limit": self._config.max_text_size},
            )
            return SkippedPayload(
                code=info.code,
                message=ReasonFormatter.format_skip(info),
                detail=info.detail,
            )

        # Read the file
        res = self._ingestor.read_text(
            entry.abs_path,
            max_size=self._config.max_text_size,
            sniff_sample=classification.sample,
        )

        if res.kind == "error":
            err = res.error or ErrorInfo(code=ErrorCode.unknown)
            return ErrorPayload(
                code=err.code,
                message=ReasonFormatter.format_error(err),
                detail=err.detail,
            )

        if res.kind == "skip":
            info = res.skipped or SkipInfo(code=SkipCode.unknown)
            return SkippedPayload(
                code=info.code,
                message=ReasonFormatter.format_skip(info),
                detail=info.detail,
            )

        text = res.text or ""
        return TextPayload(text=text, encoding=res.encoding or classification.encoding)