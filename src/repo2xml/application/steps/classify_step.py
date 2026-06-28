# src/repo2xml/application/steps/classify_step.py
from __future__ import annotations

from repo2xml.application.step import Step
from repo2xml.domain.model import ErrorCode, ProcessingInput, ProcessingResult
from repo2xml.services.classify import ClassificationEngine


class ClassifyStep(Step):
    def __init__(self, engine: ClassificationEngine) -> None:
        self._engine = engine

    def process(self, input: ProcessingInput, result: ProcessingResult) -> None:
        classification = self._engine.classify(input.entry)
        result.classification = classification

        if classification.kind == "error":
            result.should_stop = True
            result.is_success = False
            result.error_code = ErrorCode.sniff_read_error
            result.message = classification.error or "Classification failed"