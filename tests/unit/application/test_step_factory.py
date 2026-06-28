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
from repo2xml.contracts import FilePolicy
from repo2xml.services.policies import SymlinkPolicy, ModePolicy, ErrorPolicy, BinaryPolicy, TextPolicy


class TestStepFactory:
    @pytest.fixture
    def services(self) -> ProcessingServices:
        return ProcessingServices(
            classification_engine=MagicMock(),
            ingestor=MagicMock(),
        )

    @pytest.fixture
    def ingestor(self) -> MagicMock:
        return MagicMock()

    def test_create_steps_full_no_optional(self, services: ProcessingServices, ingestor: MagicMock) -> None:
        config = ExportConfig(
            mode=Mode.full,
            scan=ScanConfig(symlinks_files=SymlinkFilesMode.follow),
            binary=BinaryHandlingConfig(mode=BinaryMode.skip),
            text=TextHandlingConfig(max_text_size=1000),
            redact=RedactConfig(enabled=False),
            token=TokenCountConfig(enabled=False),
        )
        # Build policy list for full mode with symlink follow (no SymlinkPolicy)
        policies: list[FilePolicy] = [
            ErrorPolicy(),
            BinaryPolicy(config.binary, ingestor),
            TextPolicy(config.text, ingestor),
        ]
        factory = StepFactory(config, services, policies)
        steps = factory.create_steps()

        # Expect ClassifyStep and BuildPayloadStep only
        assert len(steps) == 2
        assert isinstance(steps[0], ClassifyStep)
        assert isinstance(steps[1], BuildPayloadStep)

    def test_create_steps_with_redaction(self, services: ProcessingServices, ingestor: MagicMock) -> None:
        config = ExportConfig(
            mode=Mode.full,
            scan=ScanConfig(symlinks_files=SymlinkFilesMode.follow),
            binary=BinaryHandlingConfig(mode=BinaryMode.skip),
            text=TextHandlingConfig(max_text_size=1000),
            redact=RedactConfig(enabled=True),
            token=TokenCountConfig(enabled=False),
        )
        services.redaction_engine = MagicMock()
        policies: list[FilePolicy] = [
            ErrorPolicy(),
            BinaryPolicy(config.binary, ingestor),
            TextPolicy(config.text, ingestor),
        ]
        factory = StepFactory(config, services, policies)
        steps = factory.create_steps()

        assert len(steps) == 3
        assert isinstance(steps[0], ClassifyStep)
        assert isinstance(steps[1], BuildPayloadStep)
        assert isinstance(steps[2], RedactStep)

    def test_create_steps_with_token_counting(self, services: ProcessingServices, ingestor: MagicMock) -> None:
        config = ExportConfig(
            mode=Mode.full,
            scan=ScanConfig(symlinks_files=SymlinkFilesMode.follow),
            binary=BinaryHandlingConfig(mode=BinaryMode.skip),
            text=TextHandlingConfig(max_text_size=1000),
            redact=RedactConfig(enabled=False),
            token=TokenCountConfig(enabled=True),
        )
        services.token_counter = MagicMock()
        policies: list[FilePolicy] = [
            ErrorPolicy(),
            BinaryPolicy(config.binary, ingestor),
            TextPolicy(config.text, ingestor),
        ]
        factory = StepFactory(config, services, policies)
        steps = factory.create_steps()

        assert len(steps) == 3
        assert isinstance(steps[0], ClassifyStep)
        assert isinstance(steps[1], BuildPayloadStep)
        assert isinstance(steps[2], TokenCountStep)

    def test_create_steps_with_both_optional(self, services: ProcessingServices, ingestor: MagicMock) -> None:
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
        policies: list[FilePolicy] = [
            ErrorPolicy(),
            BinaryPolicy(config.binary, ingestor),
            TextPolicy(config.text, ingestor),
        ]
        factory = StepFactory(config, services, policies)
        steps = factory.create_steps()

        assert len(steps) == 4
        assert isinstance(steps[0], ClassifyStep)
        assert isinstance(steps[1], BuildPayloadStep)
        assert isinstance(steps[2], RedactStep)
        assert isinstance(steps[3], TokenCountStep)

    def test_create_steps_with_symlink_as_link(self, services: ProcessingServices, ingestor: MagicMock) -> None:
        config = ExportConfig(
            mode=Mode.full,
            scan=ScanConfig(symlinks_files=SymlinkFilesMode.as_link),
            binary=BinaryHandlingConfig(mode=BinaryMode.skip),
            text=TextHandlingConfig(max_text_size=1000),
            redact=RedactConfig(enabled=False),
            token=TokenCountConfig(enabled=False),
        )
        policies: list[FilePolicy] = [
            SymlinkPolicy(SymlinkFilesMode.as_link),
            ErrorPolicy(),
            BinaryPolicy(config.binary, ingestor),
            TextPolicy(config.text, ingestor),
        ]
        factory = StepFactory(config, services, policies)
        steps = factory.create_steps()
        # Still only two steps: ClassifyStep and BuildPayloadStep (which now uses policies)
        assert len(steps) == 2
        assert isinstance(steps[0], ClassifyStep)
        assert isinstance(steps[1], BuildPayloadStep)

    def test_create_steps_metadata_mode(self, services: ProcessingServices, ingestor: MagicMock) -> None:
        config = ExportConfig(
            mode=Mode.metadata,
            scan=ScanConfig(),
            binary=BinaryHandlingConfig(),
            text=TextHandlingConfig(),
            redact=RedactConfig(enabled=False),
            token=TokenCountConfig(enabled=False),
        )
        # In metadata mode, only ModePolicy is used.
        policies: list[FilePolicy] = [ModePolicy(Mode.metadata)]
        factory = StepFactory(config, services, policies)
        steps = factory.create_steps()
        # Metadata mode: still ClassifyStep and BuildPayloadStep
        assert len(steps) == 2
        assert isinstance(steps[0], ClassifyStep)
        assert isinstance(steps[1], BuildPayloadStep)