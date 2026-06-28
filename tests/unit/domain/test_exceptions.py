# tests/unit/domain/test_exceptions.py
"""Unit tests for custom exceptions."""

import pytest

from repo2xml.domain.exceptions import (
    ConfigurationError,
    DeserializationError,
    FacadeError,
    OutputError,
    Repo2XMLError,
    RestoreError,
    RestoreSecurityError,
    SerializationError,
    UnsupportedPayloadError,
)


class TestExceptionHierarchy:
    def test_base_exception(self) -> None:
        """All custom exceptions must inherit from Repo2XMLError."""
        exceptions = [
            ConfigurationError,
            FacadeError,
            OutputError,
            SerializationError,
            DeserializationError,
            RestoreError,
            RestoreSecurityError,
            UnsupportedPayloadError,
        ]
        for exc_cls in exceptions:
            assert issubclass(exc_cls, Repo2XMLError)

    def test_restore_security_error_subclass(self) -> None:
        """RestoreSecurityError must be a subclass of RestoreError."""
        assert issubclass(RestoreSecurityError, RestoreError)
        assert issubclass(RestoreSecurityError, Repo2XMLError)

    def test_direct_instantiation(self) -> None:
        """Repo2XMLError can be raised directly."""
        with pytest.raises(Repo2XMLError):
            raise Repo2XMLError("base error")


class TestExceptionMessages:
    @pytest.mark.parametrize(
        ("exc_cls", "msg"),
        [
            (ConfigurationError, "invalid config"),
            (FacadeError, "facade failed"),
            (OutputError, "output error"),
            (SerializationError, "serialization error"),
            (DeserializationError, "deserialization error"),
            (RestoreError, "restore error"),
            (RestoreSecurityError, "security violation"),
            (UnsupportedPayloadError, "unsupported payload"),
        ],
    )
    def test_message_preserved(self, exc_cls, msg: str) -> None:
        exc = exc_cls(msg)
        assert str(exc) == msg

    def test_default_message(self) -> None:
        """Exception can be raised without message (args tuple empty)."""
        exc = ConfigurationError()
        assert str(exc) == ""


class TestRaiseBehaviour:
    def test_catch_base_exception(self) -> None:
        """Catching Repo2XMLError should catch all derived exceptions."""
        with pytest.raises(Repo2XMLError):
            raise ConfigurationError("config error")

    def test_catch_restore_security_as_restore(self) -> None:
        """RestoreSecurityError can be caught as RestoreError."""
        with pytest.raises(RestoreError):
            raise RestoreSecurityError("security")