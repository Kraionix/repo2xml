# src/repo2xml/application/factories.py
from __future__ import annotations

import logging
from pathlib import Path
from typing import List, Optional

from repo2xml.contracts import FilePolicy, ProgressReporter, StatsProvider, ScanUseCase
from repo2xml.application.entry_processor import EntryProcessor
from repo2xml.application.pipeline import Pipeline
from repo2xml.application.pipeline_orchestrator import PipelineOrchestrator
from repo2xml.application.services import ProcessingServices
from repo2xml.application.statistics_collector import StatisticsCollector
from repo2xml.application.step_factory import StepFactory
from repo2xml.application.writer_coordinator import WriterCoordinator
from repo2xml.application.partition import MultiStreamManager
from repo2xml.config import ExportConfig, Mode, SymlinkFilesMode
from repo2xml.services.classify import ClassificationEngine
from repo2xml.services.ingest.ingestor import StandardIngestor
from repo2xml.services.ingest.redact import RedactionEngine
from repo2xml.services.output.targets import OutputTarget
from repo2xml.services.serialize.factory import get_format_factory
from repo2xml.services.tokenize import create_token_counter
from repo2xml.services.policies import (
    SymlinkPolicy,
    ModePolicy,
    ErrorPolicy,
    BinaryPolicy,
    TextPolicy,
)

logger = logging.getLogger("repo2xml.component_factory")


class ExportComponentFactory:
    """
    Factory for creating all components needed for an export pipeline.
    """

    def __init__(
        self,
        config: ExportConfig,
        output_target: OutputTarget,
        progress: Optional[ProgressReporter] = None,
    ):
        self.config = config
        self.output_target = output_target
        self.progress = progress or self._null_reporter()

    def build(self, scan_use_case: ScanUseCase) -> tuple[PipelineOrchestrator, StatisticsCollector]:
        config = self.config
        reporter = self.progress

        # --- Ingestor ---
        ingestor = StandardIngestor(
            newline_mode=config.text.newline.value,
            decode_errors=config.text.decode_errors.value,
        )

        # --- Classification engine ---
        classification_engine = ClassificationEngine(
            Path.cwd(),  # root_path is not used by ClassificationEngine except for config discovery
            config_path=config.classify.config_path,
        )

        # --- Redaction engine (optional) ---
        redaction_engine = None
        if config.redact.enabled:
            redaction_engine = RedactionEngine(
                root_path=Path.cwd(),  # root_path only used for default config discovery
                config_path=config.redact.config_path,
            )

        # --- Token counter (optional) ---
        token_counter = None
        if config.token.enabled:
            token_counter = create_token_counter(
                "huggingface",
                model=config.token.model,
                revision=config.token.revision,
                token=config.token.token,
                trust_remote_code=config.token.trust_remote_code,
            )

        # --- Build the policy chain ---
        policies = self._build_policies(config, ingestor)

        # --- Processing services (dependencies for steps) ---
        services = ProcessingServices(
            classification_engine=classification_engine,
            ingestor=ingestor,
            redaction_engine=redaction_engine,
            token_counter=token_counter,
        )

        # --- Step factory and pipeline ---
        step_factory = StepFactory(config, services, policies)
        steps = step_factory.create_steps()
        pipeline = Pipeline(steps)
        entry_processor = EntryProcessor(pipeline)

        # --- Document writer factory for partitioning ---
        format_factory = get_format_factory(config.format)

        def document_writer_factory(**kwargs):
            return format_factory.create_document_writer(**kwargs)

        # --- WriterCoordinator or MultiStreamManager ---
        if config.partition.enabled:
            # Ensure we have a token counter for partition decisions
            if token_counter is None:
                # Create a default token counter for partitioning
                token_counter = create_token_counter(
                    "huggingface",
                    model=config.token.model or "deepseek-ai/DeepSeek-V4-Pro",
                    revision=config.token.revision or "main",
                    token=config.token.token,
                    trust_remote_code=config.token.trust_remote_code or False,
                )

            writer_coordinator = MultiStreamManager(
                config=config.partition,
                mode=config.mode,
                token_counter=token_counter,
                document_writer_factory=document_writer_factory,
                progress_reporter=reporter,
                buffer_chars=config.output.write_buffer_chars,
            )
        else:
            # --- Document writer (normal) ---
            document_writer = format_factory.create_document_writer(
                formatting=config.output.formatting.value,
                include_mtime=config.output.include_mtime,
                include_size=config.output.include_size,
                text_decode_errors=config.text.decode_errors.value,
                write_fn=lambda s: None,  # dummy, will be replaced
            )
            writer_coordinator = WriterCoordinator(
                document_writer=document_writer,
                output_target=self.output_target,
                buffer_chars=config.output.write_buffer_chars,
            )

        # --- Statistics collector ---
        providers: List[StatsProvider] = []
        providers.append(classification_engine)   # implements StatsProvider
        if redaction_engine is not None:
            providers.append(redaction_engine)    # implements StatsProvider

        collector = StatisticsCollector(
            token_counting_enabled=config.token.enabled and token_counter is not None,
            providers=providers,
        )

        # --- Pipeline orchestrator ---
        orchestrator = PipelineOrchestrator(
            config=config,
            scan_use_case=scan_use_case,
            entry_processor=entry_processor,
            writer_coordinator=writer_coordinator,
            statistics_collector=collector,
            progress_reporter=reporter,
        )

        return orchestrator, collector

    def _build_policies(self, config: ExportConfig, ingestor: StandardIngestor) -> List[FilePolicy]:
        """
        Build the ordered list of file policies based on the current configuration.
        """
        policies: List[FilePolicy] = []

        # Special case: metadata mode – only ModePolicy applies
        if config.mode == Mode.metadata:
            policies.append(ModePolicy(config.mode))
            return policies

        # For full mode, build the full chain
        # 1. Symlink handling (if not following)
        if config.scan.symlinks_files != SymlinkFilesMode.follow:
            policies.append(SymlinkPolicy(config.scan.symlinks_files))

        # 2. Error policy
        policies.append(ErrorPolicy())

        # 3. Binary policy
        policies.append(BinaryPolicy(config.binary, ingestor))

        # 4. Text policy
        policies.append(TextPolicy(config.text, ingestor))

        return policies

    @staticmethod
    def _null_reporter() -> ProgressReporter:
        from repo2xml.application.progress import NullProgressReporter
        return NullProgressReporter()