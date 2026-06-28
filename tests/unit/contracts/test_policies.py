# tests/unit/contracts/test_policies.py
"""Unit tests to verify that the FilePolicy protocol is importable."""

from repo2xml.contracts import FilePolicy


class TestFilePolicyProtocol:
    def test_import(self) -> None:
        """Verify that FilePolicy is available from contracts."""
        assert FilePolicy is not None
        # We can't instantiate a protocol, but we can check it's a class/type.
        assert isinstance(FilePolicy, type)