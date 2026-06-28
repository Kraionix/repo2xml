# src/repo2xml/application/steps/build_payload_step.py
from __future__ import annotations

from typing import List

from repo2xml.contracts import FilePolicy
from repo2xml.application.processing_context import ProcessingContext
from repo2xml.application.step import Step
from repo2xml.config import Mode
from repo2xml.domain.model import ErrorPayload, ErrorCode, SkippedPayload


class BuildPayloadStep(Step):
    """
    Step that builds the appropriate FilePayload for the file.

    This step applies a chain of FilePolicy objects in order. The first policy
    that returns a non-None payload determines the final outcome. If no policy
    matches, an ErrorPayload is returned as a fallback.
    """

    def __init__(self, policies: List[FilePolicy], mode: Mode) -> None:
        """
        Args:
            policies: Ordered list of FilePolicy instances to apply.
            mode: Export mode (used to decide whether classification is required).
        """
        self._policies = policies
        self._mode = mode

    def process(self, ctx: ProcessingContext) -> None:
        entry = ctx.entry
        classification = ctx.classification

        # In metadata mode, classification is deliberately skipped, so None is expected.
        if classification is None and self._mode != Mode.metadata:
            # Should not happen if ClassifyStep ran first (except metadata mode)
            ctx.should_stop = True
            ctx.is_success = False
            ctx.error_code = "missing_classification"
            ctx.message = "Classification result is missing"
            return

        # Apply policies in order
        payload = None
        for policy in self._policies:
            result = policy.apply(entry, classification)
            if result is not None:
                payload = result
                break

        # Fallback if no policy matched
        if payload is None:
            payload = ErrorPayload(
                code=ErrorCode.unknown,
                message="No policy matched for this file",
                detail={"entry": entry.rel_path, "kind": classification.kind if classification else "unknown"},
            )

        ctx.payload = payload

        if isinstance(payload, (SkippedPayload, ErrorPayload)):
            ctx.should_stop = True
            ctx.is_success = False
            if isinstance(payload, SkippedPayload):
                ctx.skip_code = payload.code.value
                ctx.message = payload.message
            else:
                ctx.error_code = payload.code.value
                ctx.message = payload.message
        else:
            ctx.is_success = True