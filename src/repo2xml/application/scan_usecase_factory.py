# src/repo2xml/application/scan_usecase_factory.py
"""Factory for creating ScanUseCase instances based on ScanConfig."""
from __future__ import annotations

from pathlib import Path

from repo2xml.config import (
    ScanConfig,
    FilesystemScanConfig,
    GitScanConfig,
    S3ScanConfig,
    FilterConfig,
)
from repo2xml.contracts import ScannerLike, ScanUseCase
from repo2xml.domain.exceptions import ConfigurationError
from repo2xml.services.scan.gitignore import GitignoreEngine
from repo2xml.services.scan.registry import create_scanner


class ScanUseCaseFactory:
    """Creates the appropriate ScanUseCase for a given ScanConfig."""

    def create(self, scan_config: ScanConfig, root_path: Path, filter_config: FilterConfig) -> ScanUseCase:
        if isinstance(scan_config, FilesystemScanConfig):
            return self._create_filesystem_usecase(scan_config, root_path, filter_config)
        elif isinstance(scan_config, GitScanConfig):
            # TODO: Implement GitScanUseCase when Git source is ready
            raise NotImplementedError("Git source is not yet supported")
        elif isinstance(scan_config, S3ScanConfig):
            # TODO: Implement S3ScanUseCase when S3 source is ready
            raise NotImplementedError("S3 source is not yet supported")
        else:
            raise ConfigurationError(f"Unknown scan config type: {type(scan_config)}")

    def _create_filesystem_usecase(
        self,
        config: FilesystemScanConfig,
        root_path: Path,
        filter_config: FilterConfig,
    ) -> ScanUseCase:
        from repo2xml.application.scanner_service import FilesystemScanUseCase

        # Build GitignoreEngine
        gitignore = GitignoreEngine(
            root_path=root_path,
            user_ignore=config.ignore_patterns,
            user_include=config.include_patterns,
        )

        # Build scanner using the registry
        scanner: ScannerLike = create_scanner(
            config.source,
            root_path=root_path,
            ignore_provider=gitignore,
            use_gitignore=config.use_gitignore,
            follow_symlinks_dirs=config.follow_symlinks_dirs,
            symlinks_files=config.symlinks_files.value,
            hard_exclude_dirs=set(config.hard_exclude_dirs),
        )

        return FilesystemScanUseCase(scanner=scanner, filter_config=filter_config)