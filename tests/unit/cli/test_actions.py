# tests/unit/cli/test_actions.py
"""Unit tests for CLI actions (execute_export, execute_restore)."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import typer

from repo2xml.cli.actions import execute_export, execute_restore
from repo2xml.cli.options import ExportOptions
from repo2xml.cli.ui import LogLevel
from repo2xml.config import (
    BinaryMode,
    DecodeErrors,
    Formatting,
    Mode,
    NewlineMode,
    RootPathMode,
    SymlinkFilesMode,
)
from repo2xml.domain.model import ExportStats, TokenStats
from repo2xml.services.output.targets import CompressMode


class TestExecuteExport:
    @pytest.fixture
    def console(self) -> MagicMock:
        return MagicMock()

    @pytest.fixture
    def default_options(self) -> ExportOptions:
        return ExportOptions(
            path=Path("."),
            output=Path("context.xml"),
            stdout=False,
            clipboard=False,
            stats_only=False,
            compress=CompressMode.none,
            formatting=Formatting.compact,
            mode=Mode.full,
            no_timestamp=False,
            no_mtime=False,
            no_size=False,
            root_path_mode=RootPathMode.absolute,
            dry_run=False,
            progress=False,
            report=False,
            redact=False,
            log_level="info",
            validate_xml=False,
            quiet=False,
            no_color=False,
            verbose_errors=False,
            size_min=0,
            size_max=0,
            newer_than=None,
            older_than=None,
            gitignore=True,
            ignore=None,
            include=None,
            hard_exclude=[".git"],
            follow_symlinks_dirs=False,
            symlinks_files=SymlinkFilesMode.follow,
            max_size=100000,
            binary=BinaryMode.skip,
            newline=NewlineMode.preserve,
            decode_errors=DecodeErrors.replace,
            source="filesystem",
            source_option=None,
            redact_config=None,
            classify_config=None,
            count_tokens=False,
            tokenizer_model="deepseek-ai/DeepSeek-V4-Pro",
        )

    @patch("repo2xml.cli.actions.RepoXML")
    @patch("repo2xml.cli.actions.RichProgressReporter")
    @patch("repo2xml.cli.actions.FileTarget")
    def test_execute_export_basic(self, mock_file_target, mock_progress_reporter, mock_repo_xml, default_options, console):
        """Test basic export with file output."""
        mock_engine = MagicMock()
        mock_repo_xml.return_value = mock_engine

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

        execute_export(console=console, options=default_options)

        mock_repo_xml.assert_called_once()
        mock_engine.export.assert_called_once()
        mock_file_target.assert_called_once()

    @patch("repo2xml.cli.actions.RepoXML")
    def test_execute_export_version(self, mock_repo_xml, default_options, console):
        """Test that version is handled elsewhere; we can test by checking that execute_export doesn't handle version."""
        # version is handled in main.py, so execute_export just runs.
        # We'll just ensure it doesn't raise.
        mock_engine = MagicMock()
        mock_repo_xml.return_value = mock_engine
        mock_stats = ExportStats(0, 0, 0, 0)
        mock_engine.export.return_value = mock_stats

        with patch("repo2xml.cli.actions.FileTarget") as mock_target:
            mock_target.return_value.open.return_value.__enter__ = MagicMock()
            execute_export(console=console, options=default_options)
            mock_engine.export.assert_called_once()

    @patch("repo2xml.cli.actions.RepoXML")
    def test_execute_export_dry_run(self, mock_repo_xml, default_options, console):
        """Test dry-run mode."""
        options = default_options
        options.dry_run = True
        mock_engine = MagicMock()
        mock_repo_xml.return_value = mock_engine
        mock_engine.filtered_scan.return_value = []

        execute_export(console=console, options=options)

        mock_repo_xml.assert_called_once()
        mock_engine.filtered_scan.assert_called_once()
        mock_engine.export.assert_not_called()

    @patch("repo2xml.cli.actions.RepoXML")
    def test_execute_export_stats_only(self, mock_repo_xml, default_options, console):
        """Test --stats-only mode."""
        options = default_options
        options.stats_only = True
        mock_engine = MagicMock()
        mock_repo_xml.return_value = mock_engine

        mock_stats = ExportStats(0, 0, 0, 0, token_stats=None, scan_stats=None)
        mock_engine.export.return_value = mock_stats

        with patch("repo2xml.cli.actions.DevNullTarget") as mock_devnull:
            mock_target = MagicMock()
            mock_devnull.return_value = mock_target
            mock_target.open.return_value.__enter__ = MagicMock(return_value=MagicMock())
            mock_target.open.return_value.__exit__ = MagicMock(return_value=False)

            execute_export(console=console, options=options)
            mock_devnull.assert_called_once()
            mock_engine.export.assert_called_once()

    @patch("repo2xml.cli.actions.RepoXML")
    def test_execute_export_config_error(self, mock_repo_xml, default_options, console):
        """Test configuration error handling."""
        # Simulate a configuration error by making RepoXML raise
        mock_repo_xml.side_effect = Exception("Config error")
        with pytest.raises(Exception):
            execute_export(console=console, options=default_options)

    @patch("repo2xml.cli.actions.RepoXML")
    def test_execute_export_validation_xml(self, mock_repo_xml, default_options, console):
        """Test --validate-xml flag."""
        options = default_options
        options.validate_xml = True
        mock_engine = MagicMock()
        mock_repo_xml.return_value = mock_engine

        mock_stats = ExportStats(0, 0, 0, 0, token_stats=None, scan_stats=None)
        mock_engine.export.return_value = mock_stats

        with patch("xml.etree.ElementTree.parse") as mock_parse:
            mock_parse.return_value = MagicMock()
            execute_export(console=console, options=options)
            mock_parse.assert_called_once()

    @patch("repo2xml.cli.actions.RepoXML")
    def test_execute_export_with_verbose_errors(self, mock_repo_xml, default_options, console):
        """Test that verbose_errors is passed through to reporting."""
        options = default_options
        options.verbose_errors = True
        options.report = True
        mock_engine = MagicMock()
        mock_repo_xml.return_value = mock_engine
        mock_stats = ExportStats(
            files_total=1,
            files_emitted=0,
            files_skipped=0,
            files_errors=0,
            scan_stats=MagicMock(),
        )
        mock_engine.export.return_value = mock_stats

        with patch("repo2xml.cli.actions.FileTarget") as mock_target:
            mock_target.return_value.open.return_value.__enter__ = MagicMock()
            with patch("repo2xml.cli.actions.print_scan_error_breakdown") as mock_print:
                execute_export(console=console, options=options)
                mock_print.assert_called_once()
                # Check that verbose=True was passed
                args, kwargs = mock_print.call_args
                assert kwargs.get("verbose") is True


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
        call_args = mock_repo_xml.call_args[0][0]
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
        # No exception, just ensure it runs.

    @patch("repo2xml.cli.actions.RepoXML")
    def test_execute_restore_error(self, mock_repo_xml, console):
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

    @patch("repo2xml.cli.actions.RepoXML")
    def test_execute_restore_output_is_file(self, mock_repo_xml, console, tmp_path):
        """Test that restore raises if output path exists and is a file."""
        output_file = tmp_path / "file.txt"
        output_file.touch()

        with pytest.raises(typer.Exit) as exc_info:
            execute_restore(
                console=console,
                xml_file=Path("context.xml"),
                output=output_file,
                overwrite=False,
                restore_mtime=True,
                create_empty=False,
                report=False,
                allow_absolute_symlinks=False,
                strict_validation=True,
                verbose_errors=False,
            )
        assert exc_info.value.exit_code == 2