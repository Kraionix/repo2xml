from __future__ import annotations


class Repo2XMLError(Exception):
    """Base exception for fatal repo2xml failures."""


class ConfigurationError(Repo2XMLError):
    """Invalid configuration (fatal)."""


class OutputError(Repo2XMLError):
    """Cannot open/write to the selected output target (fatal)."""


class SerializationError(Repo2XMLError):
    """Serializer selection or output generation failure (fatal)."""