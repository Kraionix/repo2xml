# tests/unit/application/test_step_factory.py
"""Unit tests for StepFactory."""

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from repo2xml.application.step_factory import StepFactory
from repo2xml.application.services import ProcessingServices
from repo2xml.application.steps.classify_step import ClassifyStep
from repo2xml.application.steps.build_payload_step import BuildPayloadStep
from repo2xml.application.steps.redact_step import RedactStep
from repo2xml.application.steps.token_count_step import TokenCountStep
from repo2xml.config import (
    BinaryHandlingConfig,
    BinaryMode,
    ExportConfig,
    Mode,
    RedactConfig,
    ScanConfig,
    SymlinkFilesMode,
    TextHandlingConfig,
    TokenCountConfig,
)


class TestStepFactory:
    @pytest.fixture
    def services(self) -> ProcessingServices:
        services = ProcessingServices(
            classification_engine=MagicMock(),
            ingestor=MagicMock(),
        )
        return services

    def test_create_steps_full_no_optional(self, services: ProcessingServices) -> None:
        config = ExportConfig(
            mode=Mode.full,
            scan=ScanConfig(symlinks_files=SymlinkFilesMode.follow),
            binary=BinaryHandlingConfig(mode=BinaryMode.skip),
            text=TextHandlingConfig(max_text_size=1000),
            redact=RedactConfig(enabled=False),
            token=TokenCountConfig(enabled=False),
        )
        factory = StepFactory(config, services)
        steps = factory.create_steps()

        # Expect ClassifyStep and BuildPayloadStep only
        assert len(steps) == 2
        assert isinstance(steps[0], ClassifyStep)
        assert isinstance(steps[1], BuildPayloadStep)

    def test_create_steps_with_redaction(self, services: ProcessingServices) -> None:
        config = ExportConfig(
            mode=Mode.full,
            scan=ScanConfig(symlinks_files=SymlinkFilesMode.follow),
            binary=BinaryHandlingConfig(mode=BinaryMode.skip),
            text=TextHandlingConfig(max_text_size=1000),
            redact=RedactConfig(enabled=True),
            token=TokenCountConfig(enabled=False),
        )
        services.redaction_engine = MagicMock()
        factory = StepFactory(config, services)
        steps = factory.create_steps()

        assert len(steps) == 3
        assert isinstance(steps[0], ClassifyStep)
        assert isinstance(steps[1], BuildPayloadStep)
        assert isinstance(steps[2], RedactStep)

    def test_create_steps_with_token_counting(self, services: ProcessingServices) -> None:
        config = ExportConfig(
            mode=Mode.full,
            scan=ScanConfig(symlinks_files=SymlinkFilesMode.follow),
            binary=BinaryHandlingConfig(mode=BinaryMode.skip),
            text=TextHandlingConfig(max_text_size=1000),
            redact=RedactConfig(enabled=False),
            token=TokenCountConfig(enabled=True),
        )
        services.token_counter = MagicMock()
        factory = StepFactory(config, services)
        steps = factory.create_steps()

        assert len(steps) == 3
        assert isinstance(steps[0], ClassifyStep)
        assert isinstance(steps[1], BuildPayloadStep)
        assert isinstance(steps[2], TokenCountStep)

    def test_create_steps_with_both_optional(self, services: ProcessingServices) -> None:
        config = ExportConfig(
            mode=Mode.full,
            scan=ScanConfig(symlinks_files=SymlinkFilesMode.follow),
            binary=BinaryHandlingConfig(mode=BinaryMode.skip),
            text=TextHandlingConfig(max_text_size=1000),
            redact=RedactConfig(enabled=True),
            token=TokenCountConfig(enabled=True),
        )
        services.redaction_engine = MagicMock()
        services.token_counter = MagicMock()
        factory = StepFactory(config, services)
        steps = factory.create_steps()

        assert len(steps) == 4
        assert isinstance(steps[0], ClassifyStep)
        assert isinstance(steps[1], BuildPayloadStep)
        assert isinstance(steps[2], RedactStep)
        assert isinstance(steps[3], TokenCountStep)

    def test_create_steps_with_symlink_as_link(self, services: ProcessingServices) -> None:
        config = ExportConfig(
            mode=Mode.full,
            scan=ScanConfig(symlinks_files=SymlinkFilesMode.as_link),
            binary=BinaryHandlingConfig(mode=BinaryMode.skip),
            text=TextHandlingConfig(max_text_size=1000),
            redact=RedactConfig(enabled=False),
            token=TokenCountConfig(enabled=False),
        )
        factory = StepFactory(config, services)
        steps = factory.create_steps()
        # BuildPayloadStep handles symlink logic internally, so no separate symlink step.
        assert len(steps) == 2
        assert isinstance(steps[1], BuildPayloadStep)

    def test_create_steps_metadata_mode(self, services: ProcessingServices) -> None:
        config = ExportConfig(
            mode=Mode.metadata,
            scan=ScanConfig(),
            binary=BinaryHandlingConfig(),
            text=TextHandlingConfig(),
            redact=RedactConfig(enabled=False),
            token=TokenCountConfig(enabled=False),
        )
        factory = StepFactory(config, services)
        steps = factory.create_steps()
        # Metadata mode: should still have ClassifyStep and BuildPayloadStep
        # BuildPayloadStep handles metadata mode internally.
        assert len(steps) == 2
        assert isinstance(steps[0], ClassifyStep)
        assert isinstance(steps[1], BuildPayloadStep)