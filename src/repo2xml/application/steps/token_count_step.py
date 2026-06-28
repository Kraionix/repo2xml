from __future__ import annotations

import logging

from repo2xml.application.processing_context import ProcessingContext
from repo2xml.application.step import Step
from repo2xml.domain.model import TextPayload
from repo2xml.services.tokenize import TokenCounter

logger = logging.getLogger("repo2xml.token_count_step")


class TokenCountStep(Step):
    """Step that counts tokens in text payloads."""

    def __init__(self, counter: TokenCounter) -> None:
        self._counter = counter

    def process(self, ctx: ProcessingContext) -> None:
        if ctx.payload is None:
            return
        if not isinstance(ctx.payload, TextPayload):
            return

        try:
            token_count = self._counter.count(ctx.payload.text, ext=ctx.entry.ext)
            ctx.token_count = token_count
        except Exception as e:
            logger.warning("Token counting failed for %s: %s", ctx.entry.rel_path, e)
            # Don't stop processing; just log and leave token_count as None.