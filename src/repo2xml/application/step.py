from __future__ import annotations

from typing import Protocol

from repo2xml.application.processing_context import ProcessingContext


class Step(Protocol):
    """Protocol for a processing step in the pipeline."""

    def process(self, ctx: ProcessingContext) -> None:
        """
        Process the given context.

        May modify ctx fields. If ctx.should_stop is set to True,
        the pipeline will halt after this step.
        """
        ...