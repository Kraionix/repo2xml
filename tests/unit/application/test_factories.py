# tests/unit/application/test_factories.py
"""Unit tests for ExportComponentFactory."""

from pathlib import Path
from unittest.mock import ANY, MagicMock, patch

import pytest

from repo2xml.application.factories import ExportComponentFactory
from repo2xml.config import (
    ExportConfig,
    Mode,
    BinaryHandlingConfig,
    TextHandlingConfig,
    ScanConfig,
    FilterConfig,
    OutputFormatConfig,
    RedactConfig,
    ClassifyConfig,
    TokenCountConfig,
)
from repo2xml.services.output.targets import OutputTarget


class TestExportComponentFactory:
    @pytest.fixture
    def config(self) -> ExportConfig:
        return ExportConfig(
            mode=Mode.full,
            format="xml",
            scan=ScanConfig(),
            filter=FilterConfig(),
            output=OutputFormatConfig(),
            binary=BinaryHandlingConfig(),
            text=TextHandlingConfig(),
            redact=RedactConfig(enabled=False),
            classify=ClassifyConfig(),
            token=TokenCountConfig(enabled=False),
        )

    @pytest.fixture
    def output_target(self) -> MagicMock:
        return MagicMock(spec=OutputTarget)

    @pytest.fixture
    def progress(self) -> MagicMock:
        return MagicMock()

    @patch("repo2xml.application.factories.create_scanner")
    @patch("repo2xml.application.factories.GitignoreEngine")
    @patch("repo2xml.application.factories.StandardIngestor")
    @patch("repo2xml.application.factories.ClassificationEngine")
    @patch("repo2xml.application.factories.RedactionEngine")
    @patch("repo2xml.application.factories.create_token_counter")
    @patch("repo2xml.application.factories.get_format_factory")
    @patch("repo2xml.application.factories.WriterCoordinator")
    @patch("repo2xml.application.factories.EntryProcessor")
    @patch("repo2xml.application.factories.PipelineOrchestrator")
    @patch("repo2xml.application.factories.StatisticsCollector")
    def test_build_all_components(
        self,
        mock_stats_collector,
        mock_orchestrator_cls,
        mock_entry_processor,
        mock_writer_coordinator,
        mock_get_format,
        mock_create_token,
        mock_redaction_engine,
        mock_classification_engine,
        mock_ingestor,
        mock_gitignore,
        mock_create_scanner,
        config,
        output_target,
        progress,
        tmp_path,
    ):
        # Mock all dependencies
        mock_scanner = MagicMock()
        mock_create_scanner.return_value = mock_scanner
        mock_gitignore.return_value = MagicMock()
        mock_ingestor.return_value = MagicMock()
        mock_classification_engine.return_value = MagicMock()
        mock_redaction_engine.return_value = MagicMock()
        mock_create_token.return_value = MagicMock()
        mock_serializer = MagicMock()
        mock_format_factory = MagicMock()
        mock_format_factory.create_serializer.return_value = mock_serializer
        mock_get_format.return_value = mock_format_factory
        mock_writer = MagicMock()
        mock_writer_coordinator.return_value = mock_writer
        mock_processor = MagicMock()
        mock_entry_processor.return_value = mock_processor
        mock_collector = MagicMock()
        mock_stats_collector.return_value = mock_collector
        mock_orchestrator = MagicMock()
        mock_orchestrator_cls.return_value = mock_orchestrator

        # Instantiate factory and build
        factory = ExportComponentFactory(config, tmp_path, output_target, progress)
        orchestrator, collector = factory.build()

        # Verify create_scanner called with correct parameters
        mock_create_scanner.assert_called_once_with(
            config.scan.source,
            root_path=tmp_path,
            ignore_provider=mock_gitignore.return_value,
            use_gitignore=config.scan.use_gitignore,
            follow_symlinks_dirs=config.scan.follow_symlinks_dirs,
            symlinks_files=config.scan.symlinks_files.value,
            hard_exclude_dirs=set(config.scan.hard_exclude_dirs),
            **config.scan.source_options,
        )

        # Verify StandardIngestor created with correct args
        mock_ingestor.assert_called_once_with(
            newline_mode=config.text.newline.value,
            decode_errors=config.text.decode_errors.value,
        )

        # Verify ClassificationEngine created
        mock_classification_engine.assert_called_once_with(
            tmp_path,
            config_path=config.classify.config_path,
        )

        # Redaction engine should not be created because redact.enabled=False
        mock_redaction_engine.assert_not_called()

        # Token counter should not be created because token.enabled=False
        mock_create_token.assert_not_called()

        # Serializer creation
        mock_format_factory.create_serializer.assert_called_once_with(
            formatting=config.output.formatting.value,
            include_mtime=config.output.include_mtime,
            include_size=config.output.include_size,
            text_decode_errors=config.text.decode_errors.value,
        )

        # WriterCoordinator creation
        mock_writer_coordinator.assert_called_once_with(
            metadata_writer=mock_serializer,
            structure_writer=mock_serializer,
            section_writer=mock_serializer,
            content_writer=mock_serializer,
            output_target=output_target,
            buffer_chars=config.output.write_buffer_chars,
        )

        # EntryProcessor creation: payload_builder is always created, so we use ANY
        mock_entry_processor.assert_called_once_with(
            config=config,
            ingestor=mock_ingestor.return_value,
            classification_engine=mock_classification_engine.return_value,
            redaction_engine=None,
            token_counter=None,
            payload_builder=ANY,  # The factory always creates a payload builder
        )

        # StatisticsCollector creation
        mock_stats_collector.assert_called_once_with(
            token_counting_enabled=False,
        )

        # PipelineOrchestrator creation
        mock_orchestrator_cls.assert_called_once_with(
            config=config,
            scanner=mock_scanner,
            entry_processor=mock_processor,
            writer_coordinator=mock_writer,
            statistics_collector=mock_collector,
            progress_reporter=progress,
            root_path=tmp_path,
        )

        # Return value
        assert orchestrator is mock_orchestrator
        assert collector is mock_collector

    @patch("repo2xml.application.factories.create_scanner")
    @patch("repo2xml.application.factories.GitignoreEngine")
    @patch("repo2xml.application.factories.StandardIngestor")
    @patch("repo2xml.application.factories.ClassificationEngine")
    @patch("repo2xml.application.factories.RedactionEngine")
    @patch("repo2xml.application.factories.create_token_counter")
    @patch("repo2xml.application.factories.get_format_factory")
    @patch("repo2xml.application.factories.WriterCoordinator")
    @patch("repo2xml.application.factories.EntryProcessor")
    @patch("repo2xml.application.factories.PipelineOrchestrator")
    @patch("repo2xml.application.factories.StatisticsCollector")
    def test_build_with_redaction_and_token_counting(
        self,
        mock_stats_collector,
        mock_orchestrator_cls,
        mock_entry_processor,
        mock_writer_coordinator,
        mock_get_format,
        mock_create_token,
        mock_redaction_engine,
        mock_classification_engine,
        mock_ingestor,
        mock_gitignore,
        mock_create_scanner,
        config,
        output_target,
        progress,
        tmp_path,
    ):
        # Enable redaction and token counting
        config.redact.enabled = True
        config.token.enabled = True

        factory = ExportComponentFactory(config, tmp_path, output_target, progress)
        factory.build()

        # Redaction engine should be created
        mock_redaction_engine.assert_called_once_with(
            root_path=tmp_path,
            config_path=config.redact.config_path,
        )

        # Token counter should be created
        mock_create_token.assert_called_once_with(
            "huggingface",
            model=config.token.model,
        )

        # EntryProcessor should receive redaction_engine and token_counter, and a payload_builder
        mock_entry_processor.assert_called_once_with(
            config=config,
            ingestor=mock_ingestor.return_value,
            classification_engine=mock_classification_engine.return_value,
            redaction_engine=mock_redaction_engine.return_value,
            token_counter=mock_create_token.return_value,
            payload_builder=ANY,  # The factory always creates a payload builder
        )

        # StatisticsCollector should have token_counting_enabled=True
        mock_stats_collector.assert_called_once_with(
            token_counting_enabled=True,
        )

    def test_build_with_custom_payload_builder(self, config, output_target, progress, tmp_path):
        # This test verifies that the factory always creates a payload builder.
        # We check that EntryProcessor receives a payload_builder (not None).
        with patch("repo2xml.application.factories.create_scanner"), \
             patch("repo2xml.application.factories.GitignoreEngine"), \
             patch("repo2xml.application.factories.StandardIngestor"), \
             patch("repo2xml.application.factories.ClassificationEngine"), \
             patch("repo2xml.application.factories.get_format_factory"), \
             patch("repo2xml.application.factories.WriterCoordinator"), \
             patch("repo2xml.application.factories.EntryProcessor") as mock_entry_processor, \
             patch("repo2xml.application.factories.PipelineOrchestrator"), \
             patch("repo2xml.application.factories.StatisticsCollector"):
            factory = ExportComponentFactory(config, tmp_path, output_target, progress)
            factory.build()
            # Check that EntryProcessor was called with a payload_builder (not None)
            call_kwargs = mock_entry_processor.call_args[1]
            assert call_kwargs.get("payload_builder") is not None

    @patch("repo2xml.application.progress.NullProgressReporter")
    @patch("repo2xml.application.factories.create_scanner")
    @patch("repo2xml.application.factories.GitignoreEngine")
    @patch("repo2xml.application.factories.StandardIngestor")
    @patch("repo2xml.application.factories.ClassificationEngine")
    @patch("repo2xml.application.factories.get_format_factory")
    @patch("repo2xml.application.factories.WriterCoordinator")
    @patch("repo2xml.application.factories.EntryProcessor")
    @patch("repo2xml.application.factories.PipelineOrchestrator")
    @patch("repo2xml.application.factories.StatisticsCollector")
    def test_null_progress_reporter(
        self,
        mock_stats_collector,
        mock_orchestrator_cls,
        mock_entry_processor,
        mock_writer_coordinator,
        mock_get_format,
        mock_classification_engine,
        mock_ingestor,
        mock_gitignore,
        mock_create_scanner,
        mock_null_reporter,
        config,
        output_target,
        tmp_path,
    ):
        # Test that if progress is None, a NullProgressReporter is created.
        mock_null_reporter.return_value = MagicMock()

        factory = ExportComponentFactory(config, tmp_path, output_target, progress=None)
        factory.build()

        # Verify that NullProgressReporter was instantiated
        mock_null_reporter.assert_called_once()
        # And that it was passed to PipelineOrchestrator
        mock_orchestrator_cls.assert_called_once()
        call_kwargs = mock_orchestrator_cls.call_args[1]
        assert call_kwargs["progress_reporter"] == mock_null_reporter.return_value