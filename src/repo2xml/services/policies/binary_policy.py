# src/repo2xml/services/policies/binary_policy.py
from __future__ import annotations

import logging
from typing import Optional

from repo2xml.contracts import FilePolicy, IngestorLike
from repo2xml.config import BinaryHandlingConfig, BinaryMode
from repo2xml.domain.formatter import ReasonFormatter
from repo2xml.domain.model import (
    BinaryBase64Payload,
    BinaryHashPayload,
    ClassificationResult,
    ErrorCode,
    ErrorInfo,
    ErrorPayload,
    FileEntry,
    FilePayload,
    SkipCode,
    SkipInfo,
    SkippedPayload,
)

logger = logging.getLogger("repo2xml.binary_policy")


class BinaryPolicy(FilePolicy):
    """
    Policy for handling binary files.

    Delegates to the configured BinaryMode:
    - `skip`: returns a SkippedPayload.
    - `hash`: returns a BinaryHashPayload (or error/skip on failure).
    - `base64`: returns a BinaryBase64Payload (or error/skip on failure).
    """

    def __init__(self, config: BinaryHandlingConfig, ingestor: IngestorLike) -> None:
        self._config = config
        self._ingestor = ingestor

    def apply(self, entry: FileEntry, classification: ClassificationResult) -> Optional[FilePayload]:
        if classification.kind != "binary":
            return None

        if self._config.mode == BinaryMode.skip:
            info = SkipInfo(code=SkipCode.binary_skip_mode)
            return SkippedPayload(
                code=info.code,
                message=ReasonFormatter.format_skip(info),
                detail=info.detail,
            )

        if self._config.mode == BinaryMode.hash:
            if self._config.max_hash_size > 0 and entry.size > self._config.max_hash_size:
                info = SkipInfo(
                    code=SkipCode.hash_size_limit,
                    detail={"size": entry.size, "limit": self._config.max_hash_size},
                )
                return SkippedPayload(
                    code=info.code,
                    message=ReasonFormatter.format_skip(info),
                    detail=info.detail,
                )
            try:
                h = self._ingestor.sha256_file(entry.abs_path)
            except OSError as e:
                err = ErrorInfo(code=ErrorCode.binary_hash_error, detail={"os_error": str(e)})
                return ErrorPayload(
                    code=err.code,
                    message=ReasonFormatter.format_error(err),
                    detail=err.detail,
                )
            return BinaryHashPayload(sha256_hex=h)

        if self._config.mode == BinaryMode.base64:
            if entry.size > self._config.max_base64_size:
                info = SkipInfo(
                    code=SkipCode.base64_size_limit,
                    detail={"size": entry.size, "limit": self._config.max_base64_size},
                )
                return SkippedPayload(
                    code=info.code,
                    message=ReasonFormatter.format_skip(info),
                    detail=info.detail,
                )
            try:
                chunks = self._ingestor.iter_base64_chunks(entry.abs_path)
            except OSError as e:
                err = ErrorInfo(code=ErrorCode.base64_error, detail={"os_error": str(e)})
                return ErrorPayload(
                    code=err.code,
                    message=ReasonFormatter.format_error(err),
                    detail=err.detail,
                )
            return BinaryBase64Payload(chunks=chunks)

        # Should not happen
        info = SkipInfo(code=SkipCode.unknown, detail={"binary_mode": str(self._config.mode)})
        return SkippedPayload(
            code=info.code,
            message=ReasonFormatter.format_skip(info),
            detail=info.detail,
        )