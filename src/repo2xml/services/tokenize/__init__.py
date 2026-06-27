# src/repo2xml/services/tokenize/__init__.py
"""
Token counting subsystem – lazy‑loaded tokenizer factories and counters.
"""

from repo2xml.services.tokenize.registry import create_token_counter, register_tokenizer_factory
from repo2xml.application.contracts import TokenCounter, TokenCounterFactory

# Hugging Face implementation – imported dynamically inside the factory
# to avoid pulling heavy dependencies at import time.
class HuggingFaceTokenizerFactory(TokenCounterFactory):
    def create(self, model: str, **kwargs) -> TokenCounter:
        from .hf_tokenizer import HuggingFaceTokenCounter
        return HuggingFaceTokenCounter(model, **kwargs)


# Register the factory under the name "huggingface".
register_tokenizer_factory("huggingface", HuggingFaceTokenizerFactory())

__all__ = [
    "create_token_counter",
    "register_tokenizer_factory",
    "TokenCounter",
    "TokenCounterFactory",
]