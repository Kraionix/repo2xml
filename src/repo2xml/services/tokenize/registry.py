# src/repo2xml/services/tokenize/registry.py
"""Registry for tokenizer factories (lazy, no heavy imports)."""

from typing import Dict, Any
from repo2xml.contracts import TokenCounter, TokenCounterFactory
from repo2xml.domain.exceptions import ConfigurationError

_TOKENIZER_FACTORY_REGISTRY: Dict[str, TokenCounterFactory] = {}


def register_tokenizer_factory(name: str, factory: TokenCounterFactory) -> None:
    """Register a tokenizer factory under a unique name."""
    if name in _TOKENIZER_FACTORY_REGISTRY:
        raise ConfigurationError(f"Tokenizer factory '{name}' already registered")
    _TOKENIZER_FACTORY_REGISTRY[name] = factory


def create_token_counter(name: str, model: str, **kwargs: Any) -> TokenCounter:
    """
    Look up a tokenizer factory and create a token counter instance.

    Args:
        name: Factory identifier (e.g., "huggingface").
        model: Model identifier (e.g., "deepseek-ai/DeepSeek-V4-Pro").
        **kwargs: Additional arguments passed to the factory.

    Returns:
        A TokenCounter instance.

    Raises:
        ConfigurationError: If the factory name is unknown.
    """
    factory = _TOKENIZER_FACTORY_REGISTRY.get(name)
    if factory is None:
        available = ", ".join(sorted(_TOKENIZER_FACTORY_REGISTRY))
        raise ConfigurationError(
            f"Unknown tokenizer type: '{name}'. Available: {available}"
        )
    return factory.create(model, **kwargs)


def list_tokenizer_factories() -> Dict[str, TokenCounterFactory]:
    """Return a copy of the current registry (for diagnostics)."""
    return dict(_TOKENIZER_FACTORY_REGISTRY)