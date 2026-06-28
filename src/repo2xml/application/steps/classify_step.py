from __future__ import annotations

from repo2xml.application.processing_context import ProcessingContext
from repo2xml.application.step import Step
from repo2xml.services.classify import ClassificationEngine


class ClassifyStep(Step):
    """Step that classifies the file (text, binary, or error)."""

    def __init__(self, engine: ClassificationEngine) -> None:
        self._engine = engine

    def process(self, ctx: ProcessingContext) -> None:
        result = self._engine.classify(ctx.entry)
        ctx.classification = result

        if result.kind == "error":
            ctx.should_stop = True
            ctx.is_success = False
            ctx.error_code = "classification_error"
            ctx.message = result.error or "Classification failed"