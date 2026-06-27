# src/repo2xml/services/tokenize/hf_tokenizer.py
"""Hugging Face tokenizer implementation with lazy loading and chunking."""

import logging
from typing import Optional, Dict, Any

from repo2xml.domain.model import TokenStats
from repo2xml.application.contracts import TokenCounter

logger = logging.getLogger("repo2xml.tokenizer")

# Chunk size in characters – large enough to be efficient, small enough to avoid OOM.
TOKENIZE_CHUNK_SIZE = 200_000


class HuggingFaceTokenCounter(TokenCounter):
    """
    Token counter using Hugging Face transformers.

    Loads the tokenizer lazily on the first call to count().
    Uses chunking for texts longer than TOKENIZE_CHUNK_SIZE.
    """

    def __init__(self, model: str, **kwargs: Any):
        self._model = model
        self._kwargs = kwargs
        self._tokenizer = None  # Will be loaded lazily

        # Internal statistics
        self._total_tokens = 0
        self._files_processed = 0
        self._files_skipped = 0
        self._tokens_by_ext: Dict[str, int] = {}
        self._max_tokens = 0
        self._min_tokens = None  # type: Optional[int]
        self._errors = 0

    def _load_tokenizer(self) -> None:
        """Import transformers and load the tokenizer (lazy)."""
        if self._tokenizer is not None:
            return
        try:
            from transformers import AutoTokenizer
        except ImportError as exc:
            raise ImportError(
                "Token counting requires transformers. "
                "Install with: pip install repo2xml[tokens]"
            ) from exc

        try:
            self._tokenizer = AutoTokenizer.from_pretrained(self._model, **self._kwargs)
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

    def get_stats(self) -> TokenStats:
        """Return the accumulated TokenStats."""
        return TokenStats(
            total_tokens=self._total_tokens,
            files_processed=self._files_processed,
            files_skipped=self._files_skipped,
            tokens_by_extension=dict(self._tokens_by_ext),
            max_tokens=self._max_tokens,
            min_tokens=self._min_tokens or 0,
            errors=self._errors,
        )