from __future__ import annotations

import logging
from typing import Optional

from repo2xml.application.pipeline import Pipeline
from repo2xml.application.processing_context import ProcessingContext
from repo2xml.application.process_result import ProcessResult
from repo2xml.domain.model import FileEntry, ErrorPayload, SkippedPayload

logger = logging.getLogger("repo2xml.entry_processor")


class EntryProcessor:
    """
    Processes a single file entry using a pipeline of steps.

    The pipeline is responsible for classification, payload building,
    redaction, token counting, and any future extensions.
    """

    def __init__(self, pipeline: Pipeline) -> None:
        self._pipeline = pipeline

    def process(self, entry: FileEntry) -> ProcessResult:
        ctx = ProcessingContext(entry=entry)
        self._pipeline.execute(ctx)

        if ctx.is_success:
            return ProcessResult(
                status="success",
                payload=ctx.payload,
                token_count=ctx.token_count,
            )
        elif ctx.skip_code is not None:
            return ProcessResult(
                status="skipped",
                skip_code=ctx.skip_code,
                message=ctx.message,
            )
        else:
            return ProcessResult(
                status="error",
                error_code=ctx.error_code or "unknown_error",
                message=ctx.message or "Processing failed",
            )