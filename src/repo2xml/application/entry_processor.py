# src/repo2xml/application/entry_processor.py
from __future__ import annotations

import logging

from repo2xml.application.pipeline import Pipeline
from repo2xml.application.process_result import ProcessResult
from repo2xml.domain.model import FileEntry, ProcessingInput

logger = logging.getLogger("repo2xml.entry_processor")


class EntryProcessor:
    """
    Processes a single file entry using a pipeline of steps.
    """

    def __init__(self, pipeline: Pipeline) -> None:
        self._pipeline = pipeline

    def process(self, entry: FileEntry) -> ProcessResult:
        input = ProcessingInput(entry=entry)
        result = self._pipeline.execute(input)

        if result.is_success:
            return ProcessResult(
                status="success",
                payload=result.payload,
                token_count=result.token_count,
            )
        elif result.skip_code is not None:
            return ProcessResult(
                status="skipped",
                skip_code=result.skip_code,
                message=result.message,
            )
        else:
            return ProcessResult(
                status="error",
                error_code=result.error_code,
                message=result.message or "Processing failed",
            )