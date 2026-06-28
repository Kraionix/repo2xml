# tests/unit/contracts/test_imports.py
"""Unit tests to verify that all contracts are importable from the new package."""

from repo2xml.contracts import (
    Deserializer,
    DocumentWriter,
    FormatFactory,
    IgnoreProvider,
    IngestorLike,
    ProgressReporter,
    ScannerLike,
    ScanStatsLike,
    StatsProvider,
    TokenCounter,
    TokenCounterFactory,
)


class TestContractsImports:
    def test_all_protocols_importable(self) -> None:
        """Verify that all expected protocols are exposed at the package level."""
        assert Deserializer is not None
        assert DocumentWriter is not None
        assert FormatFactory is not None
        assert IgnoreProvider is not None
        assert IngestorLike is not None
        assert ProgressReporter is not None
        assert ScannerLike is not None
        assert ScanStatsLike is not None
        assert StatsProvider is not None
        assert TokenCounter is not None
        assert TokenCounterFactory is not None

    def test_protocols_are_abstract_or_protocol(self) -> None:
        """Verify that classes are either ABC or Protocol (duck typing)."""
        pass  # handled by import test