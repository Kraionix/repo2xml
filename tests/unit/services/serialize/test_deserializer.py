# tests/unit/services/serialize/test_deserializer.py
"""Unit tests for XMLDeserializer."""

import xml.etree.ElementTree as ET
from io import BytesIO
from pathlib import Path

import pytest

from repo2xml.domain.exceptions import DeserializationError
from repo2xml.domain.model import (
    BinaryBase64Payload,
    BinaryHashPayload,
    ErrorPayload,
    LinkPayload,
    MetadataPayload,
    SkippedPayload,
    TextPayload,
)
from repo2xml.services.serialize.xml.deserializer import XMLDeserializer
from repo2xml.services.serialize.xml.format_spec import XmlFormatSpec


class TestXMLDeserializer:
    @pytest.fixture(autouse=True)
    def mock_xmlparser(self, monkeypatch):
        """
        Patch ET.XMLParser to accept resolve_entities and forbid_dtd arguments
        (which are not supported in Python 3.12+ but are used in the code).
        """
        original_xmlparser = ET.XMLParser

        def patched_xmlparser(*args, **kwargs):
            # Remove unsupported arguments
            kwargs.pop("resolve_entities", None)
            kwargs.pop("forbid_dtd", None)
            return original_xmlparser(*args, **kwargs)

        monkeypatch.setattr(ET, "XMLParser", patched_xmlparser)

    @pytest.fixture
    def deserializer(self) -> XMLDeserializer:
        return XMLDeserializer()

    def _make_xml(self, content: str) -> BytesIO:
        """Wrap XML content in a complete document with meta and structure."""
        full = f"""<?xml version="1.0" encoding="utf-8"?>
<repository_context version="1.2" tool_version="0.4.0">
  <meta>
    <root_path>/repo</root_path>
    <generated_at_utc>2025-01-01T00:00:00+00:00</generated_at_utc>
  </meta>
  <project_structure>
    <file name="file.txt" path="file.txt" />
  </project_structure>
  <files mode="full">
    {content}
  </files>
</repository_context>
"""
        return BytesIO(full.encode("utf-8"))

    def test_parse_metadata(self, deserializer: XMLDeserializer) -> None:
        xml = self._make_xml("")
        repo = deserializer.parse(xml, strict=False)
        assert repo.meta.root_path == "/repo"
        assert repo.meta.generated_at_utc == "2025-01-01T00:00:00+00:00"
        assert repo.meta.tool_version == "0.4.0"
        assert repo.meta.schema_version == "1.2"

    def test_parse_structure(self, deserializer: XMLDeserializer) -> None:
        xml = self._make_xml("")
        repo = deserializer.parse(xml, strict=False)
        assert len(repo.structure) == 1
        entry = repo.structure[0]
        assert entry.rel_path == "file.txt"
        assert entry.name == "file.txt"
        assert entry.size == 0
        assert entry.mtime_ns == 0

    def test_parse_text_payload(self, deserializer: XMLDeserializer) -> None:
        content = '''
<file path="file.txt" ext=".txt" size="10" mtime_utc="2020-01-01T00:00:00+00:00">
  <content encoding="utf-8" decode_errors="replace">Hello</content>
</file>
'''
        xml = self._make_xml(content)
        repo = deserializer.parse(xml, strict=False)
        files = list(repo.files)
        assert len(files) == 1
        entry, payload = files[0].entry, files[0].payload
        assert entry.rel_path == "file.txt"
        assert isinstance(payload, TextPayload)
        assert payload.text == "Hello"
        assert payload.encoding == "utf-8"

    def test_parse_binary_base64(self, deserializer: XMLDeserializer) -> None:
        content = '''
<file path="data.bin" ext=".bin" size="6" binary="true">
  <content encoding="base64">YWJjZGVm</content>
</file>
'''
        xml = self._make_xml(content)
        repo = deserializer.parse(xml, strict=False)
        files = list(repo.files)
        assert len(files) == 1
        payload = files[0].payload
        assert isinstance(payload, BinaryBase64Payload)
        assert list(payload.chunks) == ["YWJjZGVm"]

    def test_parse_binary_hash(self, deserializer: XMLDeserializer) -> None:
        content = '''
<file path="data.bin" ext=".bin" size="6" binary="true">
  <content encoding="sha256">abc123</content>
</file>
'''
        xml = self._make_xml(content)
        repo = deserializer.parse(xml, strict=False)
        files = list(repo.files)
        assert len(files) == 1
        payload = files[0].payload
        assert isinstance(payload, BinaryHashPayload)
        assert payload.sha256_hex == "abc123"

    def test_parse_link(self, deserializer: XMLDeserializer) -> None:
        content = '''
<file path="link" ext="" size="0" symlink="true" link_target="/target" link_only="true" />
'''
        xml = self._make_xml(content)
        repo = deserializer.parse(xml, strict=False)
        files = list(repo.files)
        assert len(files) == 1
        payload = files[0].payload
        assert isinstance(payload, LinkPayload)
        assert payload.link_target == "/target"

    def test_parse_skipped(self, deserializer: XMLDeserializer) -> None:
        content = '''
<file path="big.txt" ext=".txt" size="1000" skipped="true" skip_code="text_size_limit">
  <error>Too large</error>
</file>
'''
        xml = self._make_xml(content)
        repo = deserializer.parse(xml, strict=False)
        files = list(repo.files)
        assert len(files) == 1
        payload = files[0].payload
        assert isinstance(payload, SkippedPayload)
        assert payload.code == "text_size_limit"
        assert payload.message == "Too large"

    def test_parse_error(self, deserializer: XMLDeserializer) -> None:
        content = '''
<file path="bad.txt" ext=".txt" size="0" skipped="true" error_code="stat_error">
  <error>Stat failed</error>
</file>
'''
        xml = self._make_xml(content)
        repo = deserializer.parse(xml, strict=False)
        files = list(repo.files)
        assert len(files) == 1
        payload = files[0].payload
        assert isinstance(payload, ErrorPayload)
        assert payload.code == "stat_error"
        assert payload.message == "Stat failed"

    def test_parse_with_tokens_attribute(self, deserializer: XMLDeserializer) -> None:
        content = '''
<file path="file.py" ext=".py" size="100" tokens="42">
  <content encoding="utf-8">print("hello")</content>
</file>
'''
        xml = self._make_xml(content)
        repo = deserializer.parse(xml, strict=False)
        files = list(repo.files)
        assert len(files) == 1
        entry = files[0].entry
        assert entry.token_count == 42

    def test_parse_missing_files_section(self, deserializer: XMLDeserializer) -> None:
        xml = BytesIO(b'''<?xml version="1.0"?>
<repository_context version="1.2" tool_version="0.4.0">
  <meta><root_path>/repo</root_path></meta>
  <project_structure/>
</repository_context>
''')
        repo = deserializer.parse(xml, strict=False)
        files = list(repo.files)
        assert len(files) == 0

    def test_parse_malformed_xml_raises(self, deserializer: XMLDeserializer) -> None:
        xml = BytesIO(b"<not-xml>")
        with pytest.raises(DeserializationError, match="Malformed XML"):
            deserializer.parse(xml, strict=False)

    def test_parse_wrong_root_raises(self, deserializer: XMLDeserializer) -> None:
        xml = BytesIO(b'''<?xml version="1.0"?>
<wrong_root version="1.2">
  <meta><root_path>/repo</root_path></meta>
</wrong_root>
''')
        with pytest.raises(DeserializationError, match="Unexpected root element"):
            deserializer.parse(xml, strict=False)

    def test_parse_missing_meta_raises(self, deserializer: XMLDeserializer) -> None:
        xml = BytesIO(b'''<?xml version="1.0"?>
<repository_context version="1.2" tool_version="0.4.0">
  <project_structure/>
</repository_context>
''')
        with pytest.raises(DeserializationError, match="Missing <meta> element"):
            deserializer.parse(xml, strict=False)

    def test_strict_validation_passes(self, deserializer: XMLDeserializer) -> None:
        xml = self._make_xml('<file path="a.txt" ext=".txt" size="0"><content>hi</content></file>')
        repo = deserializer.parse(xml, strict=True)
        assert repo.meta.root_path == "/repo"

    def test_strict_validation_fails_on_missing_meta(self, deserializer: XMLDeserializer) -> None:
        xml = BytesIO(b'''<?xml version="1.0"?>
<repository_context version="1.2" tool_version="0.4.0">
  <project_structure/>
</repository_context>
''')
        with pytest.raises(DeserializationError, match="Missing <meta> element"):
            deserializer.parse(xml, strict=True)