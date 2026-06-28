# src/repo2xml/application/entry_processor.py
from __future__ import annotations

import logging
from typing import Optional, TYPE_CHECKING

from repo2xml.contracts import IngestorLike
from repo2xml.application.process_result import ProcessResult
from repo2xml.application.policies import ExportPayloadBuilder
from repo2xml.config import ExportConfig
from repo2xml.domain.model import ErrorPayload, FileEntry, SkippedPayload, TextPayload
from repo2xml.services.classify import ClassificationEngine
from repo2xml.services.ingest.redact import RedactionEngine
from repo2xml.services.tokenize import TokenCounter

logger = logging.getLogger("repo2xml.entry_processor")


class EntryProcessor:
    """
    Processes a single FileEntry and produces a ProcessResult.

    It applies classification, redaction (if enabled), token counting (if enabled),
    and builds the final FilePayload via ExportPayloadBuilder.
    """

    def __init__(
        self,
        config: ExportConfig,
        ingestor: IngestorLike,
        classification_engine: ClassificationEngine,
        redaction_engine: Optional[RedactionEngine] = None,
        token_counter: Optional[TokenCounter] = None,
        payload_builder: Optional[ExportPayloadBuilder] = None,
    ):
        self.config = config
        self.ingestor = ingestor
        self.classification_engine = classification_engine
        self.redaction_engine = redaction_engine
        self.token_counter = token_counter

        # Build or reuse payload builder (if not provided)
        if payload_builder is None:
            self.payload_builder = ExportPayloadBuilder(
                mode=config.mode,
                binary=config.binary,
                text=config.text,
                symlinks_files=config.scan.symlinks_files,
                ingestor=self.ingestor,
            )
        else:
            self.payload_builder = payload_builder

        self._token_counting_enabled = config.token.enabled and self.token_counter is not None

    def process(self, entry: FileEntry) -> ProcessResult:
        try:
            classification = self.classification_engine.classify(entry)
            payload = self.payload_builder.build(entry, classification)

            if isinstance(payload, SkippedPayload):
                return ProcessResult(
                    status="skipped",
                    skip_code=payload.code.value,
                    message=payload.message,
                )
            if isinstance(payload, ErrorPayload):
                return ProcessResult(
                    status="error",
                    error_code=payload.code.value,
                    message=payload.message,
                )

            # Redaction
            if self.redaction_engine is not None and isinstance(payload, TextPayload):
                new_text = self.redaction_engine.process(entry, payload.text)
                payload = TextPayload(text=new_text, encoding=payload.encoding)

            # Token counting
            token_count: Optional[int] = None
            if self._token_counting_enabled and isinstance(payload, TextPayload):
                try:
                    token_count = self.token_counter.count(payload.text, ext=entry.ext)
                except Exception as e:
                    logger.warning("Token counting failed for %s: %s", entry.rel_path, e)
                    return ProcessResult(
                        status="error",
                        error_code="tokenization_error",
                        message=f"Tokenization error: {e}",
                    )

            return ProcessResult(
                status="success",
                payload=payload,
                token_count=token_count,
            )

        except Exception as e:
            logger.exception("Unexpected error processing %s", entry.rel_path)
            return ProcessResult(
                status="error",
                error_code="processor_error",
                message=f"Unexpected error: {e}",
            )