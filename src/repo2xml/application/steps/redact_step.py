# src/repo2xml/application/steps/redact_step.py
from __future__ import annotations

from repo2xml.application.step import Step
from repo2xml.domain.model import TextPayload, ProcessingInput, ProcessingResult
from repo2xml.services.ingest.redact import RedactionEngine


class RedactStep(Step):
    def __init__(self, engine: RedactionEngine) -> None:
        self._engine = engine

    def process(self, input: ProcessingInput, result: ProcessingResult) -> None:
        if result.payload is None:
            return
        if not isinstance(result.payload, TextPayload):
            return

        redacted_text = self._engine.process(input.entry, result.payload.text)
        result.payload = TextPayload(text=redacted_text, encoding=result.payload.encoding)