# src/repo2xml/application/step.py
from __future__ import annotations

from typing import Protocol

from repo2xml.domain.model import ProcessingInput, ProcessingResult


class Step(Protocol):
    """Protocol for a processing step in the pipeline."""

    def process(self, input: ProcessingInput, result: ProcessingResult) -> None:
        """
        Process the given input and update the result.

        May set result.should_stop to True to halt further steps.
        """
        ...