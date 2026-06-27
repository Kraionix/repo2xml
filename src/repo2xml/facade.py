# src/repo2xml/facade.py
from __future__ import annotations

import io
import logging
from pathlib import Path
from typing import BinaryIO, List, Optional, Union

from repo2xml.application.contracts import IgnoreProvider, IngestorLike, ProgressReporter, ScannerLike
from repo2xml.application.export_pipeline import ExportPipeline
from repo2xml.application.filters import apply_file_filters
from repo2xml.application.restore_pipeline import RestorePipeline
from repo2xml.config import ExportConfig, RestoreConfig
from repo2xml.domain.exceptions import FacadeError, Repo2XMLError
from repo2xml.domain.model import ExportStats, FileEntry, RestoreStats
from repo2xml.services.ingest.ingestor import StandardIngestor
from repo2xml.services.classify import ClassificationEngine
from repo2xml.services.ingest.redact import RedactionEngine
from repo2xml.services.scan.gitignore import GitignoreEngine
from repo2xml.services.scan.registry import create_scanner
from repo2xml.services.tokenize import create_token_counter

logger = logging.getLogger("repo2xml.facade")


class RepoXML:
    """Unified facade for export and restore operations."""

    def __init__(self, config: Union[ExportConfig, RestoreConfig]):
        self.config = config

    def export(
        self,
        root_path: Path,
        output_stream: BinaryIO,
        *,
        progress: Optional[ProgressReporter] = None,
        dry_run: bool = False,
        stats_only: bool = False,
    ) -> ExportStats:
        if not isinstance(self.config, ExportConfig):
            raise FacadeError("Export operation requires ExportConfig")
        config: ExportConfig = self.config
        root = root_path.resolve()

        gitignore_engine: IgnoreProvider = GitignoreEngine(
            root_path=root,
            user_ignore=config.ignore_patterns,
            user_include=config.include_patterns,
        )

        scanner = create_scanner(
            config.source,
            root_path=root,
            ignore_provider=gitignore_engine,
            use_gitignore=config.use_gitignore,
            follow_symlinks_dirs=config.follow_symlinks_dirs,
            symlinks_files=config.symlinks_files.value,
            hard_exclude_dirs=set(config.hard_exclude_dirs),
            **config.source_options,
        )

        ingestor = StandardIngestor(
            newline_mode=config.newline.value,
            decode_errors=config.decode_errors.value,
        )

        classification_engine = ClassificationEngine(
            root,
            config_path=config.classify_config_path,
        )

        redaction_engine = None
        if config.redact:
            redaction_engine = RedactionEngine(
                root_path=root,
                config_path=config.redact_config_path,
            )

        # Token counter – only if enabled and not in dry-run/stats-only modes
        token_counter = None
        if config.count_tokens and not dry_run and not stats_only:
            token_counter = create_token_counter(
                "huggingface",
                model=config.tokenizer_model,
            )

        pipeline = ExportPipeline(
            root_path=root,
            config=config,
            scanner=scanner,
            ingestor=ingestor,
            classification_engine=classification_engine,
            redaction_engine=redaction_engine,
            token_counter=token_counter,
        )
        reporter = progress or _null_reporter()
        return pipeline.execute(output_stream=output_stream, progress=reporter)

    def filtered_scan(self, root_path: Path) -> List[FileEntry]:
        if not isinstance(self.config, ExportConfig):
            raise FacadeError("filtered_scan requires ExportConfig")
        config: ExportConfig = self.config
        root = root_path.resolve()

        gitignore_engine: IgnoreProvider = GitignoreEngine(
            root_path=root,
            user_ignore=config.ignore_patterns,
            user_include=config.include_patterns,
        )

        scanner = create_scanner(
            config.source,
            root_path=root,
            ignore_provider=gitignore_engine,
            use_gitignore=config.use_gitignore,
            follow_symlinks_dirs=config.follow_symlinks_dirs,
            symlinks_files=config.symlinks_files.value,
            hard_exclude_dirs=set(config.hard_exclude_dirs),
            **config.source_options,
        )

        entries = list(scanner.scan())
        entries = apply_file_filters(entries, config)
        entries.sort(key=lambda e: e.rel_path)
        return entries

    def export_to_bytes(self, root_path: Path) -> bytes:
        buf = io.BytesIO()
        self.export(root_path, buf)
        return buf.getvalue()

    def restore(
        self,
        input_stream: BinaryIO,
        output_root: Path,
        *,
        progress: Optional[ProgressReporter] = None,
    ) -> RestoreStats:
        if not isinstance(self.config, RestoreConfig):
            raise FacadeError("Restore operation requires RestoreConfig")
        pipeline = RestorePipeline(self.config)
        reporter = progress or _null_reporter()
        return pipeline.execute(input_stream, output_root, reporter)

    def restore_from_path(self, xml_path: Path, output_root: Path) -> RestoreStats:
        with open(xml_path, "rb") as fh:
            return self.restore(fh, output_root)


Repo2XML = RepoXML


def _null_reporter() -> ProgressReporter:
    from repo2xml.application.progress import NullProgressReporter
    return NullProgressReporter()