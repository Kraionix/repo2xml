# src/repo2xml/application/factories.py
"""
Component factory for export pipeline.

This module centralises the construction of all export components,
reducing complexity in the facade and improving testability.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import BinaryIO, List, Optional

from repo2xml.contracts import ProgressReporter, StatsProvider, FilePolicy
from repo2xml.application.entry_processor import EntryProcessor
from repo2xml.application.pipeline_orchestrator import PipelineOrchestrator
from repo2xml.application.policies import ExportPayloadBuilder
from repo2xml.application.statistics_collector import StatisticsCollector
from repo2xml.application.writer_coordinator import WriterCoordinator
from repo2xml.config import ExportConfig, Mode, SymlinkFilesMode
from repo2xml.services.classify import ClassificationEngine
from repo2xml.services.ingest.ingestor import StandardIngestor
from repo2xml.services.ingest.redact import RedactionEngine
from repo2xml.services.output.targets import OutputTarget
from repo2xml.services.scan.gitignore import GitignoreEngine
from repo2xml.services.scan.registry import create_scanner
from repo2xml.services.serialize.factory import get_format_factory
from repo2xml.services.tokenize import create_token_counter

# Import the new policy implementations
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

    Encapsulates the wiring logic that was previously in facade._build_export_components.
    """

    def __init__(
        self,
        config: ExportConfig,
        root_path: Path,
        output_target: OutputTarget,
        progress: Optional[ProgressReporter] = None,
    ):
        self.config = config
        self.root_path = root_path.resolve()
        self.output_target = output_target
        self.progress = progress or self._null_reporter()

    def build(self) -> tuple[PipelineOrchestrator, StatisticsCollector]:
        config = self.config
        root = self.root_path
        reporter = self.progress

        # --- Gitignore provider ---
        gitignore_engine = GitignoreEngine(
            root_path=root,
            user_ignore=config.scan.ignore_patterns,
            user_include=config.scan.include_patterns,
        )

        # --- Scanner ---
        scanner = create_scanner(
            config.scan.source,
            root_path=root,
            ignore_provider=gitignore_engine,
            use_gitignore=config.scan.use_gitignore,
            follow_symlinks_dirs=config.scan.follow_symlinks_dirs,
            symlinks_files=config.scan.symlinks_files.value,
            hard_exclude_dirs=set(config.scan.hard_exclude_dirs),
            **config.scan.source_options,
        )

        # --- Ingestor ---
        ingestor = StandardIngestor(
            newline_mode=config.text.newline.value,
            decode_errors=config.text.decode_errors.value,
        )

        # --- Classification engine ---
        classification_engine = ClassificationEngine(
            root,
            config_path=config.classify.config_path,
        )

        # --- Redaction engine (optional) ---
        redaction_engine = None
        if config.redact.enabled:
            redaction_engine = RedactionEngine(
                root_path=root,
                config_path=config.redact.config_path,
            )

        # --- Token counter (optional) ---
        token_counter = None
        if config.token.enabled:
            token_counter = create_token_counter(
                "huggingface",
                model=config.token.model,
            )

        # --- Build the policy chain ---
        policies = self._build_policies(config, ingestor)

        # --- Payload builder ---
        payload_builder = ExportPayloadBuilder(policies)

        # --- Serializer ---
        factory = get_format_factory(config.format)
        serializer = factory.create_serializer(
            formatting=config.output.formatting.value,
            include_mtime=config.output.include_mtime,
            include_size=config.output.include_size,
            text_decode_errors=config.text.decode_errors.value,
        )

        # --- Writer coordinator ---
        writer_coordinator = WriterCoordinator(
            metadata_writer=serializer,
            structure_writer=serializer,
            section_writer=serializer,
            content_writer=serializer,
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

        # --- Entry processor ---
        entry_processor = EntryProcessor(
            config=config,
            ingestor=ingestor,
            classification_engine=classification_engine,
            redaction_engine=redaction_engine,
            token_counter=token_counter,
            payload_builder=payload_builder,
        )

        # --- Pipeline orchestrator ---
        orchestrator = PipelineOrchestrator(
            config=config,
            scanner=scanner,
            entry_processor=entry_processor,
            writer_coordinator=writer_coordinator,
            statistics_collector=collector,
            progress_reporter=reporter,
            root_path=root,
        )

        return orchestrator, collector

    def _build_policies(self, config: ExportConfig, ingestor: StandardIngestor) -> List[FilePolicy]:
        """
        Build the ordered list of file policies based on the current configuration.

        The order is critical and determines which policy gets first chance to
        handle a file. The current order is:
        1. SymlinkPolicy (if not following symlinks)
        2. ModePolicy (only for metadata mode, which short-circuits)
        3. ErrorPolicy (handles classification errors)
        4. BinaryPolicy (for binary files)
        5. TextPolicy (for text files)

        For metadata mode, only ModePolicy is used (all files become MetadataPayload).
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

        # 2. Mode policy (for full mode it will always return None, but we keep it for clarity;
        #    actually we don't need it in full mode, but we can include it – it will just return None)
        #    We'll skip it because it would only add overhead; but we keep it for consistency?
        #    In the original design, ModePolicy was only for metadata. For full, it returns None.
        #    We can omit it to keep the chain clean.
        #    However, if we ever add other modes, we might need it. For now, we'll skip it.

        # 3. Error policy
        policies.append(ErrorPolicy())

        # 4. Binary policy
        policies.append(BinaryPolicy(config.binary, ingestor))

        # 5. Text policy
        policies.append(TextPolicy(config.text, ingestor))

        return policies

    @staticmethod
    def _null_reporter() -> ProgressReporter:
        from repo2xml.application.progress import NullProgressReporter
        return NullProgressReporter()