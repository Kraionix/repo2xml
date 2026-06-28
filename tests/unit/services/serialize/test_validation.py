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

    # ---- New tests for business rules ----

    def test_business_rule_binary_with_tokens(self) -> None:
        """If binary='true', tokens attribute must not be present."""
        root = self._make_root(
            '<files mode="full"><file path="data.bin" binary="true" tokens="42"/></files>'
        )
        validator = XMLStructureValidator(root)
        with pytest.raises(DeserializationError, match="binary.*tokens"):
            validator.validate()

    def test_business_rule_tokens_present_on_text_file_ok(self) -> None:
        """Tokens attribute on text file is allowed."""
        root = self._make_root(
            '<files mode="full"><file path="a.txt" tokens="42"><content>hello</content></file></files>'
        )
        validator = XMLStructureValidator(root)
        validator.validate()  # should pass

    def test_business_rule_skipped_without_error(self) -> None:
        """If skipped='true', there must be an <error> element."""
        root = self._make_root(
            '<files mode="full"><file path="a.txt" skipped="true"/></files>'
        )
        validator = XMLStructureValidator(root)
        with pytest.raises(DeserializationError, match="skipped.*missing <error>"):
            validator.validate()

    def test_business_rule_skipped_with_error_ok(self) -> None:
        """If skipped='true' and error element present, pass."""
        root = self._make_root(
            '<files mode="full"><file path="a.txt" skipped="true"><error>skip</error></file></files>'
        )
        validator = XMLStructureValidator(root)
        validator.validate()  # should pass

    def test_business_rule_base64_on_non_binary(self) -> None:
        """If content encoding is base64 but file is not marked binary, reject."""
        root = self._make_root(
            '<files mode="full"><file path="a.txt"><content encoding="base64">YWJj</content></file></files>'
        )
        validator = XMLStructureValidator(root)
        # Match the actual error message from the code
        with pytest.raises(DeserializationError, match="not marked binary but content has base64 encoding"):
            validator.validate()

    def test_business_rule_tokens_without_content_ok(self) -> None:
        """Tokens without content is fine if we don't require content."""
        root = self._make_root(
            '<files mode="full"><file path="a.txt" tokens="42"/></files>'
        )
        validator = XMLStructureValidator(root)
        validator.validate()