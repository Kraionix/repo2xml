# tests/unit/services/serialize/test_format_spec.py
"""Unit tests for format specification (XmlFormatSpec)."""

from repo2xml.domain.model import (
    BinaryBase64Payload,
    BinaryHashPayload,
    ErrorPayload,
    LinkPayload,
    MetadataPayload,
    SkippedPayload,
    TextPayload,
)
from repo2xml.services.serialize.xml.format_spec import XmlFormatSpec


class TestXmlFormatSpecClassifyPayload:
    def test_metadata_payload(self) -> None:
        attrs = {}
        content_info = None
        klass = XmlFormatSpec.classify_payload(attrs, content_info)
        assert klass is MetadataPayload

    def test_link_payload(self) -> None:
        attrs = {XmlFormatSpec.ATTR_LINK_ONLY: "true"}
        content_info = None
        klass = XmlFormatSpec.classify_payload(attrs, content_info)
        assert klass is LinkPayload

    def test_skipped_payload(self) -> None:
        attrs = {
            XmlFormatSpec.ATTR_SKIPPED: "true",
            XmlFormatSpec.ATTR_SKIP_CODE: "text_size_limit",
        }
        content_info = None
        klass = XmlFormatSpec.classify_payload(attrs, content_info)
        assert klass is SkippedPayload

    def test_skipped_without_code_should_be_error(self) -> None:
        attrs = {XmlFormatSpec.ATTR_SKIPPED: "true"}
        content_info = None
        # If skipped but no skip_code, it's considered an error payload.
        klass = XmlFormatSpec.classify_payload(attrs, content_info)
        assert klass is ErrorPayload

    def test_error_payload(self) -> None:
        attrs = {
            XmlFormatSpec.ATTR_SKIPPED: "true",
            XmlFormatSpec.ATTR_ERROR_CODE: "stat_error",
        }
        content_info = None
        klass = XmlFormatSpec.classify_payload(attrs, content_info)
        assert klass is ErrorPayload

    def test_binary_base64_payload(self) -> None:
        attrs = {XmlFormatSpec.ATTR_BINARY: "true"}
        content_info = {XmlFormatSpec.ATTR_ENCODING: "base64"}
        klass = XmlFormatSpec.classify_payload(attrs, content_info)
        assert klass is BinaryBase64Payload

    def test_binary_hash_payload(self) -> None:
        attrs = {XmlFormatSpec.ATTR_BINARY: "true"}
        content_info = {XmlFormatSpec.ATTR_ENCODING: "sha256"}
        klass = XmlFormatSpec.classify_payload(attrs, content_info)
        assert klass is BinaryHashPayload

    def test_binary_without_encoding_is_hash(self) -> None:
        attrs = {XmlFormatSpec.ATTR_BINARY: "true"}
        content_info = {}  # no encoding, defaults to hash
        klass = XmlFormatSpec.classify_payload(attrs, content_info)
        assert klass is BinaryHashPayload

    def test_text_payload(self) -> None:
        attrs = {}
        content_info = {"encoding": "utf-8"}
        klass = XmlFormatSpec.classify_payload(attrs, content_info)
        assert klass is TextPayload

    def test_text_without_content_info_metadata(self) -> None:
        attrs = {}
        content_info = None
        klass = XmlFormatSpec.classify_payload(attrs, content_info)
        assert klass is MetadataPayload