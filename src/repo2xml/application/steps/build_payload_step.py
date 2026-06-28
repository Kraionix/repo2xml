# src/repo2xml/application/steps/build_payload_step.py
from __future__ import annotations

from typing import List

from repo2xml.contracts import FilePolicy
from repo2xml.application.step import Step
from repo2xml.config import Mode
from repo2xml.domain.model import ErrorPayload, ErrorCode, SkippedPayload, ProcessingInput, ProcessingResult


class BuildPayloadStep(Step):
    def __init__(self, policies: List[FilePolicy], mode: Mode) -> None:
        self._policies = policies
        self._mode = mode

    def process(self, input: ProcessingInput, result: ProcessingResult) -> None:
        entry = input.entry
        classification = result.classification

        if classification is None and self._mode != Mode.metadata:
            result.should_stop = True
            result.is_success = False
            result.error_code = ErrorCode.unknown
            result.message = "Classification result is missing"
            return

        payload = None
        for policy in self._policies:
            res = policy.apply(entry, classification)
            if res is not None:
                payload = res
                break

        if payload is None:
            payload = ErrorPayload(
                code=ErrorCode.unknown,
                message="No policy matched for this file",
                detail={"entry": entry.rel_path, "kind": classification.kind if classification else "unknown"},
            )

        result.payload = payload

        if isinstance(payload, (SkippedPayload, ErrorPayload)):
            result.should_stop = True
            result.is_success = False
            if isinstance(payload, SkippedPayload):
                result.skip_code = payload.code
                result.message = payload.message
            else:
                result.error_code = payload.code
                result.message = payload.message
        else:
            result.is_success = True