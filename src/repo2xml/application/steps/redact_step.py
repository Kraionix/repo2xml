from __future__ import annotations

from repo2xml.application.processing_context import ProcessingContext
from repo2xml.application.step import Step
from repo2xml.domain.model import TextPayload
from repo2xml.services.ingest.redact import RedactionEngine


class RedactStep(Step):
    """Step that applies secret redaction to text payloads."""

    def __init__(self, engine: RedactionEngine) -> None:
        self._engine = engine

    def process(self, ctx: ProcessingContext) -> None:
        if ctx.payload is None:
            return
        if not isinstance(ctx.payload, TextPayload):
            return

        redacted_text = self._engine.process(ctx.entry, ctx.payload.text)
        ctx.payload = TextPayload(text=redacted_text, encoding=ctx.payload.encoding)