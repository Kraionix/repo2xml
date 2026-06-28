# src/repo2xml/domain/exceptions.py
from __future__ import annotations


class Repo2XMLError(Exception):
    """Base exception for all repo2xml failures."""


class ConfigurationError(Repo2XMLError):
    """Invalid configuration."""


class FacadeError(Repo2XMLError):
    """Error during facade initialisation or wiring."""


class OutputError(Repo2XMLError):
    """Cannot open/write to the selected output target."""


class SerializationError(Repo2XMLError):
    """Serialisation failure."""


class DeserializationError(Repo2XMLError):
    """Deserialisation failure (malformed or unsupported input)."""


class RestoreError(Repo2XMLError):
    """Failure during filesystem restore."""


class UnsupportedPayloadError(Repo2XMLError):
    """A payload type is not supported by the chosen format."""


class RestoreSecurityError(RestoreError):
    """Security violation during restore (path escape, unsafe symlink, etc.)."""