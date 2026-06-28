# tests/unit/cli/test_actions.py
"""Unit tests for CLI actions (execute_export, execute_restore)."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import typer

from repo2xml.cli.actions import execute_export, execute_restore
from repo2xml.cli.ui import LogLevel
from repo2xml.config import Formatting, Mode, RootPathMode, SymlinkFilesMode, BinaryMode, NewlineMode, DecodeErrors
from repo2xml.domain.model import ExportStats, TokenStats
from repo2xml.services.output.targets import CompressMode


class TestExecuteExport:
    @pytest.fixture
    def console(self) -> MagicMock:
        return MagicMock()

    @pytest.fixture
    def default_kwargs(self) -> dict:
        return {
            "console": MagicMock(),
            "version": False,
            "path": Path("."),
            "output": Path("context.xml"),
            "stdout": False,
            "clipboard": False,
            "stats_only": False,
            "compress": CompressMode.none,
            "formatting": Formatting.compact,
            "mode": Mode.full,
            "no_timestamp": False,
            "no_mtime": False,
            "no_size": False,
            "root_path_mode": RootPathMode.absolute,
            "dry_run": False,
            "progress": False,
            "report": False,
            "redact": False,
            "log_level": LogLevel.info,
            "validate_xml": False,
            "quiet": False,
            "no_color": False,
            "size_min": 0,
            "size_max": 0,
            "newer_than": None,
            "older_than": None,
            "gitignore": True,
            "ignore": None,
            "include": None,
            "hard_exclude": [".git"],
            "follow_symlinks_dirs": False,
            "symlinks_files": SymlinkFilesMode.follow,
            "max_size": 100000,
            "binary": BinaryMode.skip,
            "newline": NewlineMode.preserve,
            "decode_errors": DecodeErrors.replace,
            "source": "filesystem",
            "source_option": None,
            "redact_config": None,
            "classify_config": None,
            "count_tokens": False,
            "tokenizer_model": "deepseek-ai/DeepSeek-V4-Pro",
            "verbose_errors": False,
        }

    @patch("repo2xml.cli.actions.RepoXML")
    @patch("repo2xml.cli.actions.RichProgressReporter")
    @patch("repo2xml.cli.actions.FileTarget")
    def test_execute_export_basic(self, mock_file_target, mock_progress_reporter, mock_repo_xml, default_kwargs):
        """Test basic export with file output."""
        mock_engine = MagicMock()
        mock_repo_xml.return_value = mock_engine

        # Create a real ExportStats with real numeric fields to avoid formatting errors
        mock_stats = ExportStats(
            files_total=10,
            files_emitted=8,
            files_skipped=1,
            files_errors=1,
            skipped_by_code={},
            errors_by_code={},
            scan_warning_summary=None,
            redaction_stats=None,
            classification_stats=None,
            token_stats=TokenStats(total_tokens=100, files_processed=8),
            scan_stats=None,
        )
        mock_engine.export.return_value = mock_stats

        mock_target = MagicMock()
        mock_file_target.return_value = mock_target
        mock_target.open.return_value.__enter__ = MagicMock(return_value=MagicMock())
        mock_target.open.return_value.__exit__ = MagicMock(return_value=False)

        execute_export(**default_kwargs)

        mock_repo_xml.assert_called_once()
        mock_engine.export.assert_called_once()
        mock_file_target.assert_called_once()

    @patch("repo2xml.cli.actions.RepoXML")
    def test_execute_export_version(self, mock_repo_xml, default_kwargs):
        """Test --version flag."""
        kwargs = default_kwargs.copy()
        kwargs["version"] = True
        with patch("typer.echo") as mock_echo:
            with pytest.raises(typer.Exit) as exc_info:
                execute_export(**kwargs)
            assert exc_info.value.exit_code == 0
            mock_echo.assert_called_once()
            mock_repo_xml.assert_not_called()

    @patch("repo2xml.cli.actions.RepoXML")
    def test_execute_export_dry_run(self, mock_repo_xml, default_kwargs):
        """Test dry-run mode."""
        kwargs = default_kwargs.copy()
        kwargs["dry_run"] = True
        mock_engine = MagicMock()
        mock_repo_xml.return_value = mock_engine
        mock_engine.filtered_scan.return_value = []

        execute_export(**kwargs)

        mock_repo_xml.assert_called_once()
        mock_engine.filtered_scan.assert_called_once()
        mock_engine.export.assert_not_called()

    @patch("repo2xml.cli.actions.RepoXML")
    def test_execute_export_stats_only(self, mock_repo_xml, default_kwargs):
        """Test --stats-only mode."""
        kwargs = default_kwargs.copy()
        kwargs["stats_only"] = True
        mock_engine = MagicMock()
        mock_repo_xml.return_value = mock_engine

        # Create real ExportStats to avoid formatting errors
        mock_stats = ExportStats(
            files_total=0,
            files_emitted=0,
            files_skipped=0,
            files_errors=0,
            token_stats=None,
            scan_stats=None,
        )
        mock_engine.export.return_value = mock_stats

        with patch("repo2xml.cli.actions.DevNullTarget") as mock_devnull:
            mock_target = MagicMock()
            mock_devnull.return_value = mock_target
            mock_target.open.return_value.__enter__ = MagicMock(return_value=MagicMock())
            mock_target.open.return_value.__exit__ = MagicMock(return_value=False)

            execute_export(**kwargs)
            mock_devnull.assert_called_once()
            mock_engine.export.assert_called_once()

    @patch("repo2xml.cli.actions.RepoXML")
    def test_execute_export_config_error(self, mock_repo_xml, default_kwargs):
        """Test configuration error handling."""
        # Simulate a configuration error by making RepoXML raise
        mock_repo_xml.side_effect = Exception("Config error")
        with pytest.raises(Exception):
            execute_export(**default_kwargs)

    @patch("repo2xml.cli.actions.RepoXML")
    def test_execute_export_validation_xml(self, mock_repo_xml, default_kwargs):
        """Test --validate-xml flag."""
        kwargs = default_kwargs.copy()
        kwargs["validate_xml"] = True
        mock_engine = MagicMock()
        mock_repo_xml.return_value = mock_engine

        mock_stats = ExportStats(
            files_total=0,
            files_emitted=0,
            files_skipped=0,
            files_errors=0,
            token_stats=None,
            scan_stats=None,
        )
        mock_engine.export.return_value = mock_stats

        with patch("xml.etree.ElementTree.parse") as mock_parse:
            mock_parse.return_value = MagicMock()
            execute_export(**kwargs)
            mock_parse.assert_called_once()


class TestExecuteRestore:
    @pytest.fixture
    def console(self) -> MagicMock:
        return MagicMock()

    @patch("repo2xml.cli.actions.RepoXML")
    @patch("repo2xml.cli.actions.RichProgressReporter")
    def test_execute_restore_basic(self, mock_progress, mock_repo_xml, console):
        mock_engine = MagicMock()
        mock_repo_xml.return_value = mock_engine
        mock_engine.restore.return_value = MagicMock()

        execute_restore(
            console=console,
            xml_file=Path("context.xml"),
            output=Path("."),
            overwrite=False,
            restore_mtime=True,
            create_empty=False,
            report=False,
            allow_absolute_symlinks=False,
            strict_validation=True,
            verbose_errors=False,
        )

        mock_repo_xml.assert_called_once()
        # Verify that RestoreConfig was created with allow_absolute_symlinks=False
        # We can check the config passed to RepoXML by inspecting the call
        call_args = mock_repo_xml.call_args[0][0]  # first positional argument
        assert call_args.allow_absolute_symlinks is False
        assert call_args.strict_validation is True

    @patch("repo2xml.cli.actions.RepoXML")
    @patch("repo2xml.cli.actions.RichProgressReporter")
    def test_execute_restore_with_allow_absolute_symlinks(self, mock_progress, mock_repo_xml, console):
        mock_engine = MagicMock()
        mock_repo_xml.return_value = mock_engine
        mock_engine.restore.return_value = MagicMock()

        execute_restore(
            console=console,
            xml_file=Path("context.xml"),
            output=Path("."),
            overwrite=False,
            restore_mtime=True,
            create_empty=False,
            report=False,
            allow_absolute_symlinks=True,
            strict_validation=True,
            verbose_errors=False,
        )

        call_args = mock_repo_xml.call_args[0][0]
        assert call_args.allow_absolute_symlinks is True

    @patch("repo2xml.cli.actions.RepoXML")
    @patch("repo2xml.cli.actions.RichProgressReporter")
    def test_execute_restore_with_verbose_errors(self, mock_progress, mock_repo_xml, console):
        mock_engine = MagicMock()
        mock_repo_xml.return_value = mock_engine
        mock_engine.restore.return_value = MagicMock()

        # We can't easily test verbose_errors because it's used in reporting, but we can check that the
        # flag is passed through and does not cause errors.
        execute_restore(
            console=console,
            xml_file=Path("context.xml"),
            output=Path("."),
            overwrite=False,
            restore_mtime=True,
            create_empty=False,
            report=True,
            allow_absolute_symlinks=False,
            strict_validation=True,
            verbose_errors=True,
        )
        # No assertion needed; just ensure it runs without errors.

    @patch("repo2xml.cli.actions.RepoXML")
    def test_execute_restore_error(self, mock_repo_xml, console):
        # Simulate an error during restore
        mock_engine = MagicMock()
        mock_repo_xml.return_value = mock_engine
        mock_engine.restore.side_effect = Exception("Restore failed")

        with pytest.raises(typer.Exit) as exc_info:
            execute_restore(
                console=console,
                xml_file=Path("context.xml"),
                output=Path("."),
                overwrite=False,
                restore_mtime=True,
                create_empty=False,
                report=False,
                allow_absolute_symlinks=False,
                strict_validation=True,
                verbose_errors=False,
            )
        assert exc_info.value.exit_code == 1