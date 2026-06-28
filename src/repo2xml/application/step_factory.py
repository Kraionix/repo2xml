# src/repo2xml/application/step_factory.py
from __future__ import annotations

from typing import List

from repo2xml.contracts import FilePolicy
from repo2xml.application.step import Step
from repo2xml.application.services import ProcessingServices
from repo2xml.application.steps.classify_step import ClassifyStep
from repo2xml.application.steps.build_payload_step import BuildPayloadStep
from repo2xml.application.steps.redact_step import RedactStep
from repo2xml.application.steps.token_count_step import TokenCountStep
from repo2xml.config import ExportConfig, Mode


class StepFactory:
    """
    Factory that creates the ordered list of processing steps based on configuration.
    """

    def __init__(
        self,
        config: ExportConfig,
        services: ProcessingServices,
        policies: List[FilePolicy],
    ) -> None:
        self._config = config
        self._services = services
        self._policies = policies

    def create_steps(self) -> List[Step]:
        steps: List[Step] = []

        # 1. Classification (skip in metadata mode – no content analysis needed)
        if self._config.mode != Mode.metadata:
            steps.append(ClassifyStep(self._services.classification_engine))

        # 2. Build payload (using the policy chain)
        steps.append(BuildPayloadStep(self._policies, mode=self._config.mode))

        # 3. Redaction (if enabled)
        if self._config.redact.enabled and self._services.redaction_engine is not None:
            steps.append(RedactStep(self._services.redaction_engine))

        # 4. Token counting (if enabled)
        if self._config.token.enabled and self._services.token_counter is not None:
            steps.append(TokenCountStep(self._services.token_counter))

        return steps