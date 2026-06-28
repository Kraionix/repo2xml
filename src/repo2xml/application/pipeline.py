from __future__ import annotations

from typing import List

from repo2xml.application.processing_context import ProcessingContext
from repo2xml.application.step import Step


class Pipeline:
    """
    A pipeline that executes a sequence of steps.

    Steps are executed in order until one sets ctx.should_stop = True,
    at which point the pipeline halts and returns the context.
    """

    def __init__(self, steps: List[Step]) -> None:
        self._steps = steps

    def execute(self, ctx: ProcessingContext) -> ProcessingContext:
        for step in self._steps:
            step.process(ctx)
            if ctx.should_stop:
                break
        return ctx