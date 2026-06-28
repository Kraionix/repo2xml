# tests/unit/application/test_restore_pipeline.py
"""Unit tests for RestorePipeline."""

from io import BytesIO
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from repo2xml.application.restore_pipeline import RestorePipeline
from repo2xml.config import RestoreConfig


class TestRestorePipeline:
    @pytest.fixture
    def config(self) -> RestoreConfig:
        return RestoreConfig(
            overwrite=False,
            restore_mtime=True,
            create_empty_for_missing=False,
            strict_validation=True,
            allow_absolute_symlinks=False,
        )

    @patch("repo2xml.application.restore_pipeline.get_format_factory")
    def test_execute(self, mock_get_factory, config, tmp_path: Path):
        # Mock deserializer
        mock_deserializer = MagicMock()
        mock_factory = MagicMock()
        mock_factory.create_deserializer.return_value = mock_deserializer
        mock_get_factory.return_value = mock_factory

        # Mock ParsedRepository
        mock_repo = MagicMock()
        mock_repo.files = iter([])
        mock_deserializer.parse.return_value = mock_repo

        # Mock FilesystemRestorer
        mock_restorer = MagicMock()
        mock_restorer.restore.return_value = MagicMock()
        with patch("repo2xml.application.restore_pipeline.FilesystemRestorer") as mock_restorer_cls:
            mock_restorer_cls.return_value = mock_restorer

            pipeline = RestorePipeline(config)
            stream = BytesIO(b"<xml/>")
            output_root = tmp_path / "restored"
            progress = MagicMock()

            stats = pipeline.execute(stream, output_root, progress)

            # Check deserializer called with correct strict flag
            mock_deserializer.parse.assert_called_once_with(stream, strict=True)
            # Check restorer created with correct params including allow_absolute_symlinks
            mock_restorer_cls.assert_called_once_with(
                output_root,
                overwrite=False,
                skip_existing=True,
                restore_mtime=True,
                create_empty_for_missing=False,
                allow_absolute_symlinks=False,
            )
            # Check restorer called with files
            mock_restorer.restore.assert_called_once_with(mock_repo.files)
            # Progress calls
            progress.set_phase.assert_any_call("Parsing")
            progress.set_phase.assert_any_call("Restoring")
            progress.set_total.assert_called()
            progress.advance.assert_called()
            progress.finish.assert_called()

    @patch("repo2xml.application.restore_pipeline.get_format_factory")
    def test_execute_with_overwrite(self, mock_get_factory):
        config = RestoreConfig(overwrite=True, strict_validation=False, allow_absolute_symlinks=True)
        mock_deserializer = MagicMock()
        mock_factory = MagicMock()
        mock_factory.create_deserializer.return_value = mock_deserializer
        mock_get_factory.return_value = mock_factory
        mock_repo = MagicMock()
        mock_repo.files = iter([])
        mock_deserializer.parse.return_value = mock_repo

        with patch("repo2xml.application.restore_pipeline.FilesystemRestorer") as mock_restorer_cls:
            pipeline = RestorePipeline(config)
            stream = BytesIO(b"<xml/>")
            output_root = Path("/tmp/out")
            progress = MagicMock()
            pipeline.execute(stream, output_root, progress)

            # Check strict_validation=False
            mock_deserializer.parse.assert_called_once_with(stream, strict=False)
            # Check restorer created with overwrite=True, skip_existing=False, and allow_absolute_symlinks=True
            mock_restorer_cls.assert_called_once_with(
                output_root,
                overwrite=True,
                skip_existing=False,
                restore_mtime=True,
                create_empty_for_missing=False,
                allow_absolute_symlinks=True,
            )

    @patch("repo2xml.application.restore_pipeline.get_format_factory")
    def test_execute_with_create_empty(self, mock_get_factory):
        config = RestoreConfig(create_empty_for_missing=True, allow_absolute_symlinks=False)
        mock_deserializer = MagicMock()
        mock_factory = MagicMock()
        mock_factory.create_deserializer.return_value = mock_deserializer
        mock_get_factory.return_value = mock_factory
        mock_repo = MagicMock()
        mock_repo.files = iter([])
        mock_deserializer.parse.return_value = mock_repo

        with patch("repo2xml.application.restore_pipeline.FilesystemRestorer") as mock_restorer_cls:
            pipeline = RestorePipeline(config)
            stream = BytesIO(b"<xml/>")
            output_root = Path("/tmp/out")
            progress = MagicMock()
            pipeline.execute(stream, output_root, progress)

            mock_restorer_cls.assert_called_once_with(
                output_root,
                overwrite=False,
                skip_existing=True,
                restore_mtime=True,
                create_empty_for_missing=True,
                allow_absolute_symlinks=False,
            )

    @patch("repo2xml.application.restore_pipeline.get_format_factory")
    def test_execute_with_no_strict_validation(self, mock_get_factory):
        config = RestoreConfig(strict_validation=False)
        mock_deserializer = MagicMock()
        mock_factory = MagicMock()
        mock_factory.create_deserializer.return_value = mock_deserializer
        mock_get_factory.return_value = mock_factory
        mock_repo = MagicMock()
        mock_repo.files = iter([])
        mock_deserializer.parse.return_value = mock_repo

        with patch("repo2xml.application.restore_pipeline.FilesystemRestorer") as mock_restorer_cls:
            pipeline = RestorePipeline(config)
            stream = BytesIO(b"<xml/>")
            output_root = Path("/tmp/out")
            progress = MagicMock()
            pipeline.execute(stream, output_root, progress)

            mock_deserializer.parse.assert_called_once_with(stream, strict=False)