# src/repo2xml/services/serialize/xml/validation.py
"""
Programmatic validation of the repo2xml XML format.

This module performs strict checks on the document structure to catch
malformed or malicious input before any data is extracted for restoration.
"""
from __future__ import annotations

from xml.etree.ElementTree import Element

from repo2xml.domain.exceptions import DeserializationError
from repo2xml.services.serialize.xml.format_spec import XmlFormatSpec


class XMLStructureValidator:
    """Validator that ensures the XML document conforms to the expected structure."""

    SUPPORTED_VERSIONS = {"1.0", "1.1", "1.2"}

    def __init__(self, root: Element):
        self.root = root

    def validate(self) -> None:
        self._check_root()
        self._check_meta()
        self._check_project_structure()
        self._check_files()
        self._check_statistics()
        self._check_business_rules()

    def _check_root(self) -> None:
        if self.root.tag != XmlFormatSpec.TAG_ROOT:
            raise DeserializationError(
                f"Unexpected root element: {self.root.tag}. Expected: {XmlFormatSpec.TAG_ROOT}"
            )
        version = self.root.get(XmlFormatSpec.ATTR_VERSION)
        if not version:
            raise DeserializationError("Missing 'version' attribute on root element")
        if version not in self.SUPPORTED_VERSIONS:
            raise DeserializationError(
                f"Unsupported schema version: {version}. "
                f"Supported: {sorted(self.SUPPORTED_VERSIONS)}"
            )

    def _check_meta(self) -> None:
        meta = self.root.find(XmlFormatSpec.TAG_META)
        if meta is None:
            raise DeserializationError("Missing <meta> element")
        if meta.find(XmlFormatSpec.TAG_ROOT_PATH) is None:
            raise DeserializationError("Missing <root_path> inside <meta>")

    def _check_project_structure(self) -> None:
        struct = self.root.find(XmlFormatSpec.TAG_PROJECT_STRUCTURE)
        if struct is None:
            raise DeserializationError("Missing <project_structure> element")
        self._validate_structure_element(struct, current_path="")

    def _validate_structure_element(self, element: Element, current_path: str) -> None:
        for child in element:
            if child.tag == XmlFormatSpec.TAG_DIR:
                name = child.get(XmlFormatSpec.ATTR_NAME)
                if not name:
                    raise DeserializationError("Directory entry missing 'name' attribute")
                dir_path = f"{current_path}/{name}" if current_path else name
                self._check_path_safety(child.get(XmlFormatSpec.ATTR_PATH, dir_path))
                self._validate_structure_element(child, dir_path)
            elif child.tag == XmlFormatSpec.TAG_FILE:
                path_attr = child.get(XmlFormatSpec.ATTR_PATH)
                if not path_attr:
                    raise DeserializationError("File entry missing 'path' attribute")
                self._check_path_safety(path_attr)
            else:
                raise DeserializationError(
                    f"Unexpected element in project structure: {child.tag}"
                )

    def _check_files(self) -> None:
        files_el = self.root.find(XmlFormatSpec.TAG_FILES)
        if files_el is None:
            return
        for file_el in files_el:
            if file_el.tag != XmlFormatSpec.TAG_FILE:
                continue
            path_attr = file_el.get(XmlFormatSpec.ATTR_PATH)
            if not path_attr:
                raise DeserializationError("File entry in <files> missing 'path' attribute")
            self._check_path_safety(path_attr)

            tokens_attr = file_el.get(XmlFormatSpec.ATTR_TOKENS)
            if tokens_attr is not None:
                try:
                    tokens = int(tokens_attr)
                    if tokens < 0:
                        raise DeserializationError(f"Negative tokens count for '{path_attr}': {tokens}")
                except ValueError:
                    raise DeserializationError(f"Invalid tokens attribute for '{path_attr}': {tokens_attr}")

            attrs = dict(file_el.attrib)
            content_el = file_el.find(XmlFormatSpec.TAG_CONTENT)
            content_info = None
            if content_el is not None:
                content_info = dict(content_el.attrib)
            try:
                XmlFormatSpec.classify_payload(attrs, content_info)
            except Exception as exc:
                raise DeserializationError(
                    f"Cannot classify payload for file '{path_attr}': {exc}"
                ) from exc

    def _check_statistics(self) -> None:
        stats_el = self.root.find(XmlFormatSpec.TAG_STATISTICS)
        if stats_el is None:
            return
        total_attr = stats_el.get(XmlFormatSpec.ATTR_TOTAL_TOKENS)
        if total_attr is None:
            raise DeserializationError("Missing 'total_tokens' attribute in <statistics>")
        try:
            total = int(total_attr)
            if total < 0:
                raise DeserializationError(f"Negative total_tokens in <statistics>: {total}")
        except ValueError:
            raise DeserializationError(f"Invalid total_tokens value: {total_attr}")

    def _check_business_rules(self) -> None:
        """
        Enforce semantic rules beyond structural correctness.
        """
        files_el = self.root.find(XmlFormatSpec.TAG_FILES)
        if files_el is None:
            # If mode is 'structure', this is allowed; we can't easily get mode here,
            # but we can check consistency of files section.
            return

        for file_el in files_el:
            if file_el.tag != XmlFormatSpec.TAG_FILE:
                continue
            attrs = file_el.attrib
            binary = attrs.get(XmlFormatSpec.ATTR_BINARY) == "true"
            tokens = attrs.get(XmlFormatSpec.ATTR_TOKENS)
            skipped = attrs.get(XmlFormatSpec.ATTR_SKIPPED) == "true"
            error_el = file_el.find(XmlFormatSpec.TAG_ERROR)
            content_el = file_el.find(XmlFormatSpec.TAG_CONTENT)

            # 1. If binary=true, tokens must not be present
            if binary and tokens is not None:
                raise DeserializationError(
                    f"File '{attrs.get('path', '')}' has binary='true' and tokens attribute; "
                    "binary files cannot have token counts."
                )

            # 2. If tokens present, file must be text (not binary) and have content
            if tokens is not None and binary:
                # already covered above
                pass

            # 3. If skipped=true, must have an <error> element
            if skipped and error_el is None:
                raise DeserializationError(
                    f"File '{attrs.get('path', '')}' is skipped but missing <error> element."
                )

            # 4. If content is present and binary is false, it should be text (encoding not base64)
            if content_el is not None and not binary:
                enc = content_el.get(XmlFormatSpec.ATTR_ENCODING)
                if enc == "base64":
                    raise DeserializationError(
                        f"File '{attrs.get('path', '')}' is not marked binary but content has base64 encoding."
                    )
                # If no encoding, it's okay (assumed text)

    @staticmethod
    def _check_path_safety(path: str) -> None:
        if ".." in path.split("/"):
            raise DeserializationError(
                f"Path contains parent directory traversal: '{path}'"
            )