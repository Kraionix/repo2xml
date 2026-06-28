# tests/unit/cli/test_main.py
"""Unit tests for CLI entry point (main callback and restore command)."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from repo2xml.cli.main import app


class TestCliMain:
    @pytest.fixture
    def runner(self) -> CliRunner:
        return CliRunner()

    def test_version(self, runner: CliRunner):
        result = runner.invoke(app, ["--version"])
        assert result.exit_code == 0
        assert "repo2xml" in result.stdout

    def test_help(self, runner: CliRunner):
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        assert "repo2xml" in result.stdout
        assert "restore" in result.stdout

    @patch("repo2xml.cli.main.setup_logging")
    @patch("repo2xml.cli.main.Console")
    @patch("repo2xml.cli.main.execute_export")
    def test_main_default_command(self, mock_execute_export, mock_console, mock_setup_logging, runner: CliRunner):
        """Test that main callback calls execute_export with ExportOptions."""
        mock_execute_export.return_value = None
        mock_console.return_value = MagicMock()
        mock_setup_logging.return_value = MagicMock()

        result = runner.invoke(app, ["."])
        assert result.exit_code == 0, f"Unexpected exit code: {result.exit_code}, output: {result.output}"
        assert mock_execute_export.called
        # Check that the first argument is a console and second is options
        call_args = mock_execute_export.call_args[1]
        assert "options" in call_args
        options = call_args["options"]
        assert options.path == Path(".")

    @patch("repo2xml.cli.main.setup_logging")
    @patch("repo2xml.cli.main.Console")
    @patch("repo2xml.cli.main.execute_export")
    def test_main_with_options(self, mock_execute_export, mock_console, mock_setup_logging, runner: CliRunner):
        """Test that options are passed to execute_export via ExportOptions."""
        mock_execute_export.return_value = None
        mock_console.return_value = MagicMock()
        mock_setup_logging.return_value = MagicMock()

        result = runner.invoke(app, [".", "--output", "out.xml", "--redact-secrets", "--count-tokens"])
        assert result.exit_code == 0, f"Unexpected exit code: {result.exit_code}, output: {result.output}"
        assert mock_execute_export.called
        options = mock_execute_export.call_args[1]["options"]
        assert options.output == Path("out.xml")
        assert options.redact is True
        assert options.count_tokens is True

    @patch("repo2xml.cli.main.setup_logging")
    @patch("repo2xml.cli.main.Console")
    @patch("repo2xml.cli.main.execute_restore")
    def test_restore_command(self, mock_execute_restore, mock_console, mock_setup_logging, runner: CliRunner):
        mock_execute_restore.return_value = None
        mock_console.return_value = MagicMock()
        mock_setup_logging.return_value = MagicMock()

        result = runner.invoke(app, ["restore", "context.xml", "-o", "restored"])
        assert result.exit_code == 0, f"Unexpected exit code: {result.exit_code}, output: {result.output}"
        assert mock_execute_restore.called
        mock_execute_restore.assert_called_once_with(
            console=mock_console.return_value,
            xml_file=Path("context.xml"),
            output=Path("restored"),
            overwrite=False,
            restore_mtime=True,
            create_empty=False,
            report=False,
            strict_validation=True,
            allow_absolute_symlinks=False,
            verbose_errors=False,
        )

    @patch("repo2xml.cli.main.setup_logging")
    @patch("repo2xml.cli.main.Console")
    @patch("repo2xml.cli.main.execute_restore")
    def test_restore_with_overwrite(self, mock_execute_restore, mock_console, mock_setup_logging, runner: CliRunner):
        mock_execute_restore.return_value = None
        mock_console.return_value = MagicMock()
        mock_setup_logging.return_value = MagicMock()

        result = runner.invoke(app, ["restore", "context.xml", "--overwrite"])
        assert result.exit_code == 0, f"Unexpected exit code: {result.exit_code}, output: {result.output}"
        assert mock_execute_restore.called
        call_kwargs = mock_execute_restore.call_args[1]
        assert call_kwargs["overwrite"] is True

    @patch("repo2xml.cli.main.setup_logging")
    @patch("repo2xml.cli.main.Console")
    @patch("repo2xml.cli.main.execute_restore")
    def test_restore_with_allow_absolute_symlinks(self, mock_execute_restore, mock_console, mock_setup_logging, runner: CliRunner):
        mock_execute_restore.return_value = None
        mock_console.return_value = MagicMock()
        mock_setup_logging.return_value = MagicMock()

        result = runner.invoke(app, ["restore", "context.xml", "--allow-absolute-symlinks"])
        assert result.exit_code == 0, f"Unexpected exit code: {result.exit_code}, output: {result.output}"
        assert mock_execute_restore.called
        call_kwargs = mock_execute_restore.call_args[1]
        assert call_kwargs["allow_absolute_symlinks"] is True

    @patch("repo2xml.cli.main.setup_logging")
    @patch("repo2xml.cli.main.Console")
    @patch("repo2xml.cli.main.execute_restore")
    def test_restore_with_no_strict_validation(self, mock_execute_restore, mock_console, mock_setup_logging, runner: CliRunner):
        mock_execute_restore.return_value = None
        mock_console.return_value = MagicMock()
        mock_setup_logging.return_value = MagicMock()

        result = runner.invoke(app, ["restore", "context.xml", "--no-strict-validation"])
        assert result.exit_code == 0, f"Unexpected exit code: {result.exit_code}, output: {result.output}"
        assert mock_execute_restore.called
        call_kwargs = mock_execute_restore.call_args[1]
        assert call_kwargs["strict_validation"] is False

    @patch("repo2xml.cli.main.setup_logging")
    @patch("repo2xml.cli.main.Console")
    @patch("repo2xml.cli.main.execute_restore")
    def test_restore_with_verbose_errors(self, mock_execute_restore, mock_console, mock_setup_logging, runner: CliRunner):
        mock_execute_restore.return_value = None
        mock_console.return_value = MagicMock()
        mock_setup_logging.return_value = MagicMock()

        result = runner.invoke(app, ["restore", "context.xml", "--verbose-errors"])
        assert result.exit_code == 0, f"Unexpected exit code: {result.exit_code}, output: {result.output}"
        assert mock_execute_restore.called
        call_kwargs = mock_execute_restore.call_args[1]
        assert call_kwargs["verbose_errors"] is True