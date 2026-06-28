# src/repo2xml/application/pipeline.py
from __future__ import annotations

from typing import List

from repo2xml.application.step import Step
from repo2xml.domain.model import ProcessingInput, ProcessingResult


class Pipeline:
    """
    A pipeline that executes a sequence of steps.

    Steps are executed in order until one sets result.should_stop = True,
    at which point the pipeline halts and returns the result.
    """

    def __init__(self, steps: List[Step]) -> None:
        self._steps = steps

    def execute(self, input: ProcessingInput) -> ProcessingResult:
        result = ProcessingResult()
        for step in self._steps:
            step.process(input, result)
            if result.should_stop:
                break
        return result