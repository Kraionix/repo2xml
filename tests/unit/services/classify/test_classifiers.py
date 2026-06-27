# tests/unit/services/classify/test_classifiers.py
"""Unit tests for classification classifiers and helpers."""

from pathlib import Path

import pytest

from repo2xml.services.classify.classifiers import (
    ExtensionClassifier,
    detect_bom,
    looks_binary,
)


class TestExtensionClassifier:
    @pytest.fixture
    def classifier(self) -> ExtensionClassifier:
        text_exts = frozenset({".txt", ".py", ".md"})
        binary_exts = frozenset({".png", ".jpg", ".bin"})
        compound = frozenset({".tar.gz", ".tar.bz2"})
        return ExtensionClassifier(text_exts, binary_exts, compound)

    def test_text_extension(self, classifier: ExtensionClassifier) -> None:
        assert classifier.classify(Path("file.txt")) == "text"
        assert classifier.classify(Path("script.py")) == "text"
        assert classifier.classify(Path("README.md")) == "text"

    def test_binary_extension(self, classifier: ExtensionClassifier) -> None:
        assert classifier.classify(Path("image.png")) == "binary"
        assert classifier.classify(Path("photo.jpg")) == "binary"
        assert classifier.classify(Path("data.bin")) == "binary"

    def test_compound_binary_suffix(self, classifier: ExtensionClassifier) -> None:
        assert classifier.classify(Path("archive.tar.gz")) == "binary"
        assert classifier.classify(Path("archive.tar.bz2")) == "binary"

    def test_unknown_extension_returns_none(self, classifier: ExtensionClassifier) -> None:
        assert classifier.classify(Path("file.unknown")) is None

    def test_no_extension_returns_none(self, classifier: ExtensionClassifier) -> None:
        assert classifier.classify(Path("file")) is None

    def test_case_insensitive(self, classifier: ExtensionClassifier) -> None:
        assert classifier.classify(Path("file.TXT")) == "text"
        assert classifier.classify(Path("image.PNG")) == "binary"
        assert classifier.classify(Path("archive.TAR.GZ")) == "binary"


class TestDetectBom:
    def test_utf8_bom(self) -> None:
        data = b"\xef\xbb\xbfHello"
        assert detect_bom(data) == "utf-8-sig"

    def test_utf16_le_bom(self) -> None:
        data = b"\xff\xfeH\x00e\x00"
        assert detect_bom(data) == "utf-16-le"

    def test_utf16_be_bom(self) -> None:
        data = b"\xfe\xff\x00H\x00e"
        assert detect_bom(data) == "utf-16-be"

    def test_utf32_le_bom(self) -> None:
        data = b"\xff\xfe\x00\x00H\x00\x00\x00"
        assert detect_bom(data) == "utf-32-le"

    def test_utf32_be_bom(self) -> None:
        data = b"\x00\x00\xfe\xff\x00\x00\x00H"
        assert detect_bom(data) == "utf-32-be"

    def test_no_bom(self) -> None:
        data = b"Hello"
        assert detect_bom(data) is None

    def test_empty_data(self) -> None:
        assert detect_bom(b"") is None


class TestLooksBinary:
    def test_empty_data(self) -> None:
        assert looks_binary(b"", None) is False

    def test_text_data(self) -> None:
        data = b"Hello, world!\nThis is text."
        assert looks_binary(data, None) is False

    def test_binary_data_with_null(self) -> None:
        data = b"Hello\x00world"
        assert looks_binary(data, None) is True

    def test_high_ratio_nontext(self) -> None:
        # More than 30% non-text bytes
        data = b"\x00\x01\x02\x03" + b"abcd"  # 4 binary, 4 text -> 50%
        assert looks_binary(data, None, threshold=0.30) is True

    def test_low_ratio_nontext(self) -> None:
        # Even a single null byte makes it binary in the current implementation
        data = b"\x00" + b"a" * 100  # ~1% binary, but contains null
        assert looks_binary(data, None, threshold=0.30) is True

    def test_utf16_bom_bypass(self) -> None:
        # With UTF-16 BOM, should return False (bypass)
        data = b"\xff\xfeH\x00e\x00"  # UTF-16 LE BOM
        assert looks_binary(data, "utf-16-le") is False

    def test_utf32_bom_bypass(self) -> None:
        data = b"\xff\xfe\x00\x00H\x00\x00\x00"
        assert looks_binary(data, "utf-32-le") is False

    def test_custom_threshold(self) -> None:
        # Even with null bytes, binary detection triggers before ratio check
        data = b"\x00\x01" + b"a" * 8  # 20% binary, but contains null
        assert looks_binary(data, None, threshold=0.30) is True