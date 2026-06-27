# tests/unit/services/serialize/test_validation.py
"""Unit tests for XMLStructureValidator."""

import xml.etree.ElementTree as ET

import pytest

from repo2xml.domain.exceptions import DeserializationError
from repo2xml.services.serialize.xml.format_spec import XmlFormatSpec
from repo2xml.services.serialize.xml.validation import XMLStructureValidator


class TestXMLStructureValidator:
    def _make_root(self, xml_str: str) -> ET.Element:
        """Parse a complete document and return the root."""
        full = f"""<?xml version="1.0"?>
<repository_context version="1.2" tool_version="0.4.0">
  <meta><root_path>/repo</root_path></meta>
  <project_structure/>
  {xml_str}
</repository_context>
"""
        root = ET.fromstring(full)
        return root

    def test_valid_document_passes(self) -> None:
        root = self._make_root("<files mode='full'><file path='a.txt'/></files>")
        validator = XMLStructureValidator(root)
        validator.validate()  # should not raise

    def test_missing_version(self) -> None:
        root = ET.fromstring('<repository_context><meta><root_path>/repo</root_path></meta></repository_context>')
        validator = XMLStructureValidator(root)
        with pytest.raises(DeserializationError, match="Missing 'version' attribute"):
            validator.validate()

    def test_unsupported_version(self) -> None:
        root = ET.fromstring('<repository_context version="0.9"><meta><root_path>/repo</root_path></meta></repository_context>')
        validator = XMLStructureValidator(root)
        with pytest.raises(DeserializationError, match="Unsupported schema version"):
            validator.validate()

    def test_missing_meta(self) -> None:
        root = ET.fromstring('<repository_context version="1.2"/>')
        validator = XMLStructureValidator(root)
        with pytest.raises(DeserializationError, match="Missing <meta> element"):
            validator.validate()

    def test_missing_root_path_in_meta(self) -> None:
        root = ET.fromstring('<repository_context version="1.2"><meta></meta></repository_context>')
        validator = XMLStructureValidator(root)
        with pytest.raises(DeserializationError, match="Missing <root_path> inside <meta>"):
            validator.validate()

    def test_missing_project_structure(self) -> None:
        root = ET.fromstring('<repository_context version="1.2"><meta><root_path>/repo</root_path></meta></repository_context>')
        validator = XMLStructureValidator(root)
        with pytest.raises(DeserializationError, match="Missing <project_structure> element"):
            validator.validate()

    def test_project_structure_with_path_traversal(self) -> None:
        root = ET.fromstring('''<repository_context version="1.2">
            <meta><root_path>/repo</root_path></meta>
            <project_structure>
                <file path="../escape.txt" name="escape.txt"/>
            </project_structure>
        </repository_context>''')
        validator = XMLStructureValidator(root)
        with pytest.raises(DeserializationError, match="Path contains parent directory traversal"):
            validator.validate()

    def test_files_with_path_traversal(self) -> None:
        root = ET.fromstring('''<repository_context version="1.2">
            <meta><root_path>/repo</root_path></meta>
            <project_structure/>
            <files mode="full">
                <file path="../bad.txt"/>
            </files>
        </repository_context>''')
        validator = XMLStructureValidator(root)
        with pytest.raises(DeserializationError, match="Path contains parent directory traversal"):
            validator.validate()

    def test_files_missing_path(self) -> None:
        root = ET.fromstring('''<repository_context version="1.2">
            <meta><root_path>/repo</root_path></meta>
            <project_structure/>
            <files mode="full">
                <file name="no-path"/>
            </files>
        </repository_context>''')
        validator = XMLStructureValidator(root)
        with pytest.raises(DeserializationError, match="missing 'path' attribute"):
            validator.validate()

    def test_tokens_negative(self) -> None:
        root = ET.fromstring('''<repository_context version="1.2">
            <meta><root_path>/repo</root_path></meta>
            <project_structure/>
            <files mode="full">
                <file path="a.txt" tokens="-5"/>
            </files>
        </repository_context>''')
        validator = XMLStructureValidator(root)
        with pytest.raises(DeserializationError, match="Negative tokens"):
            validator.validate()

    def test_tokens_invalid_int(self) -> None:
        root = ET.fromstring('''<repository_context version="1.2">
            <meta><root_path>/repo</root_path></meta>
            <project_structure/>
            <files mode="full">
                <file path="a.txt" tokens="abc"/>
            </files>
        </repository_context>''')
        validator = XMLStructureValidator(root)
        with pytest.raises(DeserializationError, match="Invalid tokens"):
            validator.validate()

    def test_statistics_missing_total_tokens(self) -> None:
        root = ET.fromstring('''<repository_context version="1.2">
            <meta><root_path>/repo</root_path></meta>
            <project_structure/>
            <statistics/>
        </repository_context>''')
        validator = XMLStructureValidator(root)
        with pytest.raises(DeserializationError, match="Missing 'total_tokens' attribute"):
            validator.validate()

    def test_statistics_negative_total(self) -> None:
        root = ET.fromstring('''<repository_context version="1.2">
            <meta><root_path>/repo</root_path></meta>
            <project_structure/>
            <statistics total_tokens="-1"/>
        </repository_context>''')
        validator = XMLStructureValidator(root)
        with pytest.raises(DeserializationError, match="Negative total_tokens"):
            validator.validate()

    def test_invalid_element_in_project_structure(self) -> None:
        root = ET.fromstring('''<repository_context version="1.2">
            <meta><root_path>/repo</root_path></meta>
            <project_structure>
                <invalid/>
            </project_structure>
        </repository_context>''')
        validator = XMLStructureValidator(root)
        with pytest.raises(DeserializationError, match="Unexpected element in project structure"):
            validator.validate()