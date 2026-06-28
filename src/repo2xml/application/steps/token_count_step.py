# src/repo2xml/application/steps/token_count_step.py
from __future__ import annotations

import logging

from repo2xml.application.step import Step
from repo2xml.domain.model import TextPayload, ProcessingInput, ProcessingResult
from repo2xml.services.tokenize import TokenCounter

logger = logging.getLogger("repo2xml.token_count_step")


class TokenCountStep(Step):
    def __init__(self, counter: TokenCounter) -> None:
        self._counter = counter

    def process(self, input: ProcessingInput, result: ProcessingResult) -> None:
        if result.payload is None:
            return
        if not isinstance(result.payload, TextPayload):
            return

        try:
            token_count = self._counter.count(result.payload.text, ext=input.entry.ext)
            result.token_count = token_count
        except Exception as e:
            logger.warning("Token counting failed for %s: %s", input.entry.rel_path, e)