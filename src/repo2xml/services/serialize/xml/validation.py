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

    # Supported schema versions that can be parsed
    SUPPORTED_VERSIONS = {"1.0", "1.1"}

    def __init__(self, root: Element):
        """
        Args:
            root: The root element of the parsed XML tree.
        """
        self.root = root

    def validate(self) -> None:
        """
        Run all validation checks. Raises DeserializationError on first failure.
        """
        self._check_root()
        self._check_meta()
        self._check_project_structure()
        self._check_files()
        # Additional checks can be added here as the schema evolves

    def _check_root(self) -> None:
        """Verify the root element tag and schema version."""
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
        """Ensure the <meta> element is present and has required children."""
        meta = self.root.find(XmlFormatSpec.TAG_META)
        if meta is None:
            raise DeserializationError("Missing <meta> element")
        # root_path is mandatory for reliable restoration
        if meta.find(XmlFormatSpec.TAG_ROOT_PATH) is None:
            raise DeserializationError("Missing <root_path> inside <meta>")

    def _check_project_structure(self) -> None:
        """
        Validate the <project_structure> section:
        - Must be present.
        - May be empty.
        - Only <dir> and <file> elements allowed.
        - Path attributes must not contain path traversal (..).
        """
        struct = self.root.find(XmlFormatSpec.TAG_PROJECT_STRUCTURE)
        if struct is None:
            raise DeserializationError("Missing <project_structure> element")
        self._validate_structure_element(struct, current_path="")

    def _validate_structure_element(self, element: Element, current_path: str) -> None:
        """Recursively check directory and file entries."""
        for child in element:
            if child.tag == XmlFormatSpec.TAG_DIR:
                name = child.get(XmlFormatSpec.ATTR_NAME)
                if not name:
                    raise DeserializationError("Directory entry missing 'name' attribute")
                # Build new path for context (not stored, just used for error messages)
                dir_path = f"{current_path}/{name}" if current_path else name
                # Prevent path traversal attempts
                self._check_path_safety(child.get(XmlFormatSpec.ATTR_PATH, dir_path))
                # Recurse into subdirectories
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
        """
        Validate the <files> section if present (mandatory for non-structure modes).
        - Every <file> must have a 'path' attribute.
        - Path must not contain '..'.
        - The combination of attributes must allow payload classification.
        """
        files_el = self.root.find(XmlFormatSpec.TAG_FILES)
        if files_el is None:
            # Could be a structure-only export; that's fine
            return

        for file_el in files_el:
            if file_el.tag != XmlFormatSpec.TAG_FILE:
                continue  # skip non-file elements (should not happen)
            path_attr = file_el.get(XmlFormatSpec.ATTR_PATH)
            if not path_attr:
                raise DeserializationError("File entry in <files> missing 'path' attribute")
            self._check_path_safety(path_attr)

            # Attempt to classify the payload; this verifies that the attribute
            # combination is valid (no contradictory flags).
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

    @staticmethod
    def _check_path_safety(path: str) -> None:
        """
        Reject paths that attempt to escape the repository root via '..'.
        This is a basic safety net; final security is ensured by the restorer.
        """
        if ".." in path.split("/"):
            raise DeserializationError(
                f"Path contains parent directory traversal: '{path}'"
            )