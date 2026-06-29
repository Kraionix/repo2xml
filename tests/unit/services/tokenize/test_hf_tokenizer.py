"""Unit tests for HuggingFaceTokenCounter with two-phase loading and token handling."""

import warnings
warnings.filterwarnings(
    "ignore",
    message="builtin type SwigPy.* has no __module__",
    category=DeprecationWarning,
)

import logging
import os
from unittest.mock import MagicMock, patch

import pytest

from repo2xml.services.tokenize.hf_tokenizer import (
    HuggingFaceTokenCounter,
    TOKENIZE_CHUNK_SIZE,
    _WARNING_PRINTED,
)


class TestHuggingFaceTokenCounter:
    """Test suite for HuggingFaceTokenCounter."""

    def test_initialization_defaults(self):
        """Test default initialization and environment variable fallback."""
        with patch.dict(os.environ, {}, clear=True):
            counter = HuggingFaceTokenCounter("test-model")
            assert counter._model == "test-model"
            assert counter._revision == "main"
            assert counter._token is None
            assert counter._trust_remote_code is False
            assert counter._tokenizer is None

    def test_initialization_with_token_param(self):
        """Test explicit token parameter takes precedence."""
        with patch.dict(os.environ, {"HF_TOKEN": "env-token"}):
            counter = HuggingFaceTokenCounter("test-model", token="explicit-token")
            assert counter._token == "explicit-token"

    def test_initialization_with_env_token(self):
        """Test fallback to HF_TOKEN environment variable."""
        with patch.dict(os.environ, {"HF_TOKEN": "env-token"}):
            counter = HuggingFaceTokenCounter("test-model")
            assert counter._token == "env-token"

    def test_initialization_with_all_params(self):
        """Test all constructor parameters are stored."""
        counter = HuggingFaceTokenCounter(
            model="custom/model",
            revision="v1.0",
            token="abc123",
            trust_remote_code=True,
        )
        assert counter._model == "custom/model"
        assert counter._revision == "v1.0"
        assert counter._token == "abc123"
        assert counter._trust_remote_code is True

    @patch("transformers.AutoTokenizer")
    def test_two_phase_loading_local_first_success(self, mock_auto_tokenizer):
        """Test that local_files_only is attempted first and succeeds."""
        mock_tokenizer = MagicMock()
        mock_auto_tokenizer.from_pretrained.return_value = mock_tokenizer

        counter = HuggingFaceTokenCounter("test-model")
        counter._load_tokenizer()

        # First call: local_files_only=True
        mock_auto_tokenizer.from_pretrained.assert_any_call(
            "test-model",
            use_fast=True,
            revision="main",
            token=None,
            trust_remote_code=False,
            local_files_only=True,
        )
        # Should not call network load
        assert mock_auto_tokenizer.from_pretrained.call_count == 1
        assert counter._tokenizer is mock_tokenizer

    @patch("transformers.AutoTokenizer")
    def test_two_phase_loading_local_fail_network_success(self, mock_auto_tokenizer):
        """Test fallback to network when local load fails."""
        mock_tokenizer = MagicMock()
        # First call raises OSError, second returns tokenizer
        mock_auto_tokenizer.from_pretrained.side_effect = [
            OSError("not found"),
            mock_tokenizer,
        ]

        counter = HuggingFaceTokenCounter("test-model")
        counter._load_tokenizer()

        # Two calls: local then network
        assert mock_auto_tokenizer.from_pretrained.call_count == 2
        # Check first call had local_files_only=True
        first_call = mock_auto_tokenizer.from_pretrained.call_args_list[0]
        assert first_call.kwargs.get("local_files_only") is True
        # Check second call has optimised parameters
        second_call = mock_auto_tokenizer.from_pretrained.call_args_list[1]
        assert second_call.kwargs.get("local_files_only") is None
        assert second_call.kwargs.get("force_download") is False
        assert second_call.kwargs.get("resume_download") is False
        assert counter._tokenizer is mock_tokenizer

    @patch("transformers.AutoTokenizer")
    def test_load_failure_raises(self, mock_auto_tokenizer):
        """Test that network failure raises RuntimeError."""
        # Local attempt fails with OSError, network attempt fails with generic Exception
        mock_auto_tokenizer.from_pretrained.side_effect = [
            OSError("not found"),
            Exception("network error"),
        ]

        counter = HuggingFaceTokenCounter("test-model")
        with pytest.raises(RuntimeError, match="Failed to load tokenizer 'test-model'"):
            counter._load_tokenizer()

    def test_missing_import(self):
        """Test ImportError handling."""
        original_import = __import__

        def import_hook(name, *args, **kwargs):
            if name == "transformers":
                raise ImportError("no transformers")
            return original_import(name, *args, **kwargs)

        with patch("builtins.__import__", side_effect=import_hook):
            counter = HuggingFaceTokenCounter("test-model")
            with pytest.raises(ImportError, match="requires transformers"):
                counter._load_tokenizer()

    @patch("transformers.AutoTokenizer")
    def test_one_time_warning_when_no_token(self, mock_auto_tokenizer, caplog):
        """Test that missing-token warning is printed only once."""
        # Reset the module-level flag before test
        import repo2xml.services.tokenize.hf_tokenizer as hf_module
        hf_module._WARNING_PRINTED = False

        # First call: local fails, then network succeeds
        mock_tokenizer = MagicMock()
        mock_auto_tokenizer.from_pretrained.side_effect = [
            OSError("not found"),
            mock_tokenizer,
        ]

        counter = HuggingFaceTokenCounter("test-model")
        with caplog.at_level(logging.WARNING):
            counter._load_tokenizer()
            assert "No HF_TOKEN provided" in caplog.text
            caplog.clear()

        # Second call on same instance: tokenizer already loaded, no warning
        with caplog.at_level(logging.WARNING):
            counter._load_tokenizer()  # This will return immediately
            assert "No HF_TOKEN provided" not in caplog.text

    @patch("transformers.AutoTokenizer")
    def test_token_priority_explicit_over_env(self, mock_auto_tokenizer):
        """Test that explicit token is used even if HF_TOKEN is set."""
        mock_tokenizer = MagicMock()
        mock_auto_tokenizer.from_pretrained.return_value = mock_tokenizer

        with patch.dict(os.environ, {"HF_TOKEN": "env-token"}):
            counter = HuggingFaceTokenCounter("test-model", token="explicit-token")
            counter._load_tokenizer()

            # Check token was passed to from_pretrained
            call_kwargs = mock_auto_tokenizer.from_pretrained.call_args[1]
            assert call_kwargs.get("token") == "explicit-token"

    @patch("transformers.AutoTokenizer")
    def test_trust_remote_code_passed(self, mock_auto_tokenizer):
        """Test that trust_remote_code is propagated."""
        mock_tokenizer = MagicMock()
        mock_auto_tokenizer.from_pretrained.return_value = mock_tokenizer

        counter = HuggingFaceTokenCounter("test-model", trust_remote_code=True)
        counter._load_tokenizer()

        call_kwargs = mock_auto_tokenizer.from_pretrained.call_args[1]
        assert call_kwargs.get("trust_remote_code") is True

    @patch("transformers.AutoTokenizer")
    def test_revision_passed(self, mock_auto_tokenizer):
        """Test that revision is propagated."""
        mock_tokenizer = MagicMock()
        mock_auto_tokenizer.from_pretrained.return_value = mock_tokenizer

        counter = HuggingFaceTokenCounter("test-model", revision="custom-branch")
        counter._load_tokenizer()

        call_kwargs = mock_auto_tokenizer.from_pretrained.call_args[1]
        assert call_kwargs.get("revision") == "custom-branch"

    @patch("transformers.AutoTokenizer")
    def test_count_simple(self, mock_auto_tokenizer):
        """Test token counting with a short text."""
        mock_tokenizer = MagicMock()
        mock_tokenizer.encode.return_value = [1, 2, 3]  # 3 tokens
        mock_auto_tokenizer.from_pretrained.return_value = mock_tokenizer

        counter = HuggingFaceTokenCounter("test-model")
        token_count = counter.count("hello world")

        assert token_count == 3
        mock_tokenizer.encode.assert_called_once_with("hello world", add_special_tokens=False)

    @patch("transformers.AutoTokenizer")
    def test_count_chunking(self, mock_auto_tokenizer):
        """Test chunking for texts longer than TOKENIZE_CHUNK_SIZE."""
        mock_tokenizer = MagicMock()
        # Simulate tokenization: each chunk returns 10 tokens
        mock_tokenizer.encode.return_value = [0] * 10
        mock_auto_tokenizer.from_pretrained.return_value = mock_tokenizer

        # Create text longer than chunk size
        long_text = "a" * (TOKENIZE_CHUNK_SIZE + 100)
        counter = HuggingFaceTokenCounter("test-model")
        token_count = counter.count(long_text)

        # Should have been called twice: first chunk and remainder
        assert mock_tokenizer.encode.call_count == 2
        assert token_count == 20  # 2 chunks * 10 tokens

    @patch("transformers.AutoTokenizer")
    def test_count_updates_stats(self, mock_auto_tokenizer):
        """Test that stats are updated correctly."""
        mock_tokenizer = MagicMock()
        mock_tokenizer.encode.return_value = [0] * 5
        mock_auto_tokenizer.from_pretrained.return_value = mock_tokenizer

        counter = HuggingFaceTokenCounter("test-model")
        counter.count("text1", ext=".py")
        counter.count("text2", ext=".md")
        counter.count("text3", ext=".py")  # 6 tokens

        stats = counter.get_stats()
        assert stats.total_tokens == 15
        assert stats.files_processed == 3
        assert stats.files_skipped == 0
        assert stats.errors == 0
        assert stats.tokens_by_extension == {".py": 10, ".md": 5}
        assert stats.max_tokens == 5
        assert stats.min_tokens == 5  # all equal

    @patch("transformers.AutoTokenizer")
    def test_count_handles_exception(self, mock_auto_tokenizer):
        """Test that exceptions during encoding are caught and stats updated."""
        mock_tokenizer = MagicMock()
        mock_tokenizer.encode.side_effect = Exception("encode error")
        mock_auto_tokenizer.from_pretrained.return_value = mock_tokenizer

        counter = HuggingFaceTokenCounter("test-model")
        result = counter.count("text", ext=".py")

        assert result == 0
        stats = counter.get_stats()
        assert stats.files_processed == 0
        assert stats.files_skipped == 1
        assert stats.errors == 1
        assert stats.total_tokens == 0

    @patch("transformers.AutoTokenizer")
    def test_get_stats_before_count(self, mock_auto_tokenizer):
        """Test that stats are empty before any counting."""
        counter = HuggingFaceTokenCounter("test-model")
        stats = counter.get_stats()
        assert stats.total_tokens == 0
        assert stats.files_processed == 0
        assert stats.files_skipped == 0
        assert stats.tokens_by_extension == {}
        assert stats.max_tokens == 0
        assert stats.min_tokens == 0
        assert stats.errors == 0

    def test_logger_level_set(self):
        """Test that transformers logger level is set to WARNING."""
        with patch("repo2xml.services.tokenize.hf_tokenizer.logging.getLogger") as mock_get_logger:
            mock_logger = MagicMock()
            mock_get_logger.return_value = mock_logger

            # Create an instance to trigger the logger setup
            counter = HuggingFaceTokenCounter("test-model")

            mock_get_logger.assert_called_with("transformers")
            mock_logger.setLevel.assert_called_with(logging.WARNING)