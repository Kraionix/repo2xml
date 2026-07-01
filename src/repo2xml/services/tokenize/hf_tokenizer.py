# src/repo2xml/services/tokenize/hf_tokenizer.py
"""Hugging Face tokenizer implementation with lazy loading and chunking."""

import logging
import os
from typing import Any, Dict, Optional

from repo2xml.contracts import TokenCounter
from repo2xml.domain.model import TokenStats, ExportStats
from repo2xml.utils.logging_utils import temporary_logger_level

logger = logging.getLogger("repo2xml.tokenizer")

# Chunk size in characters – large enough to be efficient, small enough to avoid OOM.
TOKENIZE_CHUNK_SIZE = 200_000

# Module‑level flag to print the missing‑token warning only once.
_WARNING_PRINTED = False


class HuggingFaceTokenCounter(TokenCounter):
    """
    Token counter using Hugging Face transformers.

    Loads the tokenizer lazily on the first call to count().
    Uses chunking for texts longer than TOKENIZE_CHUNK_SIZE.
    Supports two‑phase loading: local cache first, then network.
    """

    def __init__(
        self,
        model: str,
        revision: str = "main",
        token: Optional[str] = None,
        trust_remote_code: bool = False,
        **kwargs: Any,
    ) -> None:
        self._model = model
        self._revision = revision
        self._trust_remote_code = trust_remote_code
        self._token = token or os.getenv("HF_TOKEN")
        self._kwargs = kwargs  # Kept for forward compatibility

        self._tokenizer = None  # Will be loaded lazily

        # Internal statistics
        self._total_tokens = 0
        self._files_processed = 0
        self._files_skipped = 0
        self._tokens_by_ext: Dict[str, int] = {}
        self._max_tokens = 0
        self._min_tokens: Optional[int] = None
        self._errors = 0

    def _load_tokenizer(self) -> None:
        """
        Import transformers and load the tokenizer lazily.

        Implements two‑phase loading:
            1. Attempt local_files_only=True (cache‑only).
            2. On failure, load from the network with explicit parameters.
        """
        if self._tokenizer is not None:
            return

        try:
            from transformers import AutoTokenizer
        except ImportError as exc:
            raise ImportError(
                "Token counting requires transformers. "
                "Install with: pip install repo2xml[tokens]"
            ) from exc

        # Temporary suppress internal transformers warnings (e.g., missing token).
        with temporary_logger_level("transformers", logging.WARNING):
            # Attempt 1: load from local cache only.
            try:
                self._tokenizer = AutoTokenizer.from_pretrained(
                    self._model,
                    use_fast=True,
                    revision=self._revision,
                    token=self._token,
                    trust_remote_code=self._trust_remote_code,
                    local_files_only=True,
                )
                logger.debug("Tokenizer loaded from local cache: %s", self._model)
                return
            except (OSError, EnvironmentError) as e:
                logger.debug("Tokenizer not found locally: %s", e)
                # Fall through to network load.

            # Print a one‑time warning about missing token (only if we are about to hit the network).
            global _WARNING_PRINTED
            if self._token is None and not _WARNING_PRINTED:
                logger.warning(
                    "No HF_TOKEN provided. Set HF_TOKEN environment variable or use --hf-token "
                    "to increase rate limits and speed up downloads."
                )
                _WARNING_PRINTED = True

            # Attempt 2: load from the network with optimised parameters.
            try:
                self._tokenizer = AutoTokenizer.from_pretrained(
                    self._model,
                    use_fast=True,
                    revision=self._revision,
                    token=self._token,
                    trust_remote_code=self._trust_remote_code,
                    force_download=False,
                    resume_download=False,
                )
                logger.info("Tokenizer downloaded and cached: %s", self._model)
            except Exception as exc:
                raise RuntimeError(f"Failed to load tokenizer '{self._model}': {exc}") from exc

    def count(self, text: str, ext: str = "") -> int:
        """Return the number of tokens in the text, updating internal stats."""
        self._load_tokenizer()

        try:
            if len(text) > TOKENIZE_CHUNK_SIZE:
                # Chunked tokenization
                total = 0
                for i in range(0, len(text), TOKENIZE_CHUNK_SIZE):
                    chunk = text[i:i + TOKENIZE_CHUNK_SIZE]
                    total += len(self._tokenizer.encode(chunk, add_special_tokens=False))
                token_count = total
            else:
                token_count = len(self._tokenizer.encode(text, add_special_tokens=False))

            # Update stats
            self._total_tokens += token_count
            self._files_processed += 1
            if ext:
                self._tokens_by_ext[ext] = self._tokens_by_ext.get(ext, 0) + token_count
            if token_count > self._max_tokens:
                self._max_tokens = token_count
            if self._min_tokens is None or token_count < self._min_tokens:
                self._min_tokens = token_count

            return token_count

        except Exception as exc:
            logger.warning("Tokenization error for file (ext=%s): %s", ext, exc)
            self._errors += 1
            self._files_skipped += 1
            return 0

    def apply_to(self, stats: ExportStats) -> None:
        """Apply accumulated token statistics to ExportStats."""
        stats.token_stats = TokenStats(
            total_tokens=self._total_tokens,
            files_processed=self._files_processed,
            files_skipped=self._files_skipped,
            tokens_by_extension=dict(self._tokens_by_ext),
            max_tokens=self._max_tokens,
            min_tokens=self._min_tokens or 0,
            errors=self._errors,
        )