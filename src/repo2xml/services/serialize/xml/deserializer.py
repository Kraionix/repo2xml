# src/repo2xml/services/serialize/xml/deserializer.py
from __future__ import annotations

import base64
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import BinaryIO, Iterator, List, Optional, Tuple
from xml.etree import ElementTree as ET

from repo2xml.contracts import Deserializer
from repo2xml.domain.exceptions import DeserializationError
from repo2xml.domain.model import (
    BinaryBase64Payload,
    BinaryHashPayload,
    ErrorCode,
    ErrorInfo,
    ErrorPayload,
    ExportMeta,
    FileEntry,
    FilePayload,
    LinkPayload,
    MetadataPayload,
    ParsedRepository,
    RestoreEntry,
    SkipCode,
    SkipInfo,
    SkippedPayload,
    TextPayload,
)
from repo2xml.services.serialize.xml.format_spec import XmlFormatSpec
from repo2xml.services.serialize.xml.validation import XMLStructureValidator
from repo2xml.utils.version import tool_version

logger = logging.getLogger("repo2xml.deserializer")


class XMLDeserializer(Deserializer):
    """Deserialise the repo2xml XML format into a ParsedRepository."""

    def __init__(self) -> None:
        self._spec = XmlFormatSpec

    def parse(self, stream: BinaryIO, *, strict: bool = False) -> ParsedRepository:
        """
        Parse an XML stream into a ParsedRepository.

        If `strict` is True, the document is validated against structural rules
        before data extraction. A secure XML parser is always used to prevent
        entity expansion and external entity attacks.
        """
        # Use a secure parser that disables DTD and external entities
        parser = ET.XMLParser(
            target=ET.TreeBuilder(),
            resolve_entities=False,
            forbid_dtd=True,      # Prevent DOCTYPE declarations entirely
        )
        try:
            tree = ET.parse(stream, parser=parser)
        except ET.ParseError as e:
            raise DeserializationError(f"Malformed XML: {e}") from e
        root = tree.getroot()

        if strict:
            # Perform full structural validation before touching the data
            validator = XMLStructureValidator(root)
            validator.validate()

        # Proceed with normal data extraction
        if root.tag != self._spec.TAG_ROOT:
            raise DeserializationError(f"Unexpected root element: {root.tag}")

        meta = self._parse_meta(root)
        structure = self._parse_structure(root)
        files_iter = self._parse_files(root)

        return ParsedRepository(meta=meta, structure=structure, files=files_iter)

    def _parse_meta(self, root: ET.Element) -> ExportMeta:
        meta_el = root.find(self._spec.TAG_META)
        if meta_el is None:
            raise DeserializationError("Missing <meta> element")
        root_path_el = meta_el.find(self._spec.TAG_ROOT_PATH)
        root_path = root_path_el.text if root_path_el is not None else "."
        generated_at_el = meta_el.find(self._spec.TAG_GENERATED_AT)
        generated_at = generated_at_el.text if generated_at_el is not None else None

        schema_version = root.get(self._spec.ATTR_VERSION, "unknown")
        tool = root.get(self._spec.ATTR_TOOL_VERSION, "unknown")

        return ExportMeta(
            root_path=root_path or ".",
            generated_at_utc=generated_at,
            tool_version=tool,
            schema_version=schema_version,
        )

    def _parse_structure(self, root: ET.Element) -> List[FileEntry]:
        struct_el = root.find(self._spec.TAG_PROJECT_STRUCTURE)
        if struct_el is None:
            return []
        entries: List[FileEntry] = []
        self._walk_structure(struct_el, entries, "")
        return entries

    def _walk_structure(self, parent: ET.Element, entries: List[FileEntry], current_dir: str) -> None:
        for child in parent:
            if child.tag == self._spec.TAG_DIR:
                dir_name = child.get(self._spec.ATTR_NAME, "")
                new_dir = f"{current_dir}/{dir_name}" if current_dir else dir_name
                self._walk_structure(child, entries, new_dir)
            elif child.tag == self._spec.TAG_FILE:
                file_name = child.get(self._spec.ATTR_NAME, "")
                rel_path = child.get(self._spec.ATTR_PATH) or (f"{current_dir}/{file_name}" if current_dir else file_name)
                size = int(child.get(self._spec.ATTR_SIZE, "0"))
                mtime_str = child.get(self._spec.ATTR_MTIME)
                mtime_ns = self._parse_mtime(mtime_str)
                is_symlink = child.get(self._spec.ATTR_SYMLINK) == "true"
                link_target = child.get(self._spec.ATTR_LINK_TARGET)
                # token_count is only present in <files>, not in structure, so leave None
                entries.append(FileEntry(
                    abs_path=Path(rel_path),
                    rel_path=rel_path,
                    name=file_name,
                    size=size,
                    mtime_ns=mtime_ns,
                    is_symlink=is_symlink,
                    symlink_target=link_target,
                    token_count=None,   # no token info in structure
                ))

    @staticmethod
    def _parse_mtime(iso_string: Optional[str]) -> int:
        if not iso_string:
            return 0
        try:
            dt = datetime.fromisoformat(iso_string)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return int(dt.timestamp() * 1_000_000_000)
        except Exception:
            logger.warning("Failed to parse mtime string: %r, returning 0", iso_string)
            return 0

    def _parse_files(self, root: ET.Element) -> Iterator[RestoreEntry]:
        files_el = root.find(self._spec.TAG_FILES)
        if files_el is None:
            return
        for file_el in files_el:
            if file_el.tag != self._spec.TAG_FILE:
                continue
            entry = self._parse_file_entry(file_el)
            payload = self._parse_payload(file_el)
            yield RestoreEntry(entry=entry, payload=payload)

    def _parse_file_entry(self, el: ET.Element) -> FileEntry:
        rel_path = el.get(self._spec.ATTR_PATH, "")
        name = rel_path.rsplit("/", 1)[-1] if "/" in rel_path else rel_path
        size = int(el.get(self._spec.ATTR_SIZE, "0"))
        mtime_ns = self._parse_mtime(el.get(self._spec.ATTR_MTIME))
        is_symlink = el.get(self._spec.ATTR_SYMLINK) == "true"
        link_target = el.get(self._spec.ATTR_LINK_TARGET)
        token_attr = el.get(self._spec.ATTR_TOKENS)
        token_count = int(token_attr) if token_attr is not None else None
        return FileEntry(
            abs_path=Path(rel_path),
            rel_path=rel_path,
            name=name,
            size=size,
            mtime_ns=mtime_ns,
            is_symlink=is_symlink,
            symlink_target=link_target,
            token_count=token_count,
        )

    def _parse_payload(self, el: ET.Element) -> FilePayload:
        attrs = {k: v for k, v in el.attrib.items()}
        content_el = el.find(self._spec.TAG_CONTENT)
        content_info = None
        if content_el is not None:
            content_info = {k: v for k, v in content_el.attrib.items()}
            content_info["text"] = content_el.text or ""
        payload_type = self._spec.classify_payload(attrs, content_info)

        if payload_type is MetadataPayload:
            return MetadataPayload()
        elif payload_type is LinkPayload:
            return LinkPayload(link_target=el.get(self._spec.ATTR_LINK_TARGET))
        elif payload_type is TextPayload:
            text = content_info.get("text", "") if content_info else ""
            encoding = content_info.get(self._spec.ATTR_ENCODING) if content_info else None
            return TextPayload(text=text, encoding=encoding)
        elif payload_type is BinaryBase64Payload:
            raw = content_info.get("text", "") if content_info else ""
            return BinaryBase64Payload(chunks=[raw])
        elif payload_type is BinaryHashPayload:
            sha = content_info.get("text", "") if content_info else ""
            return BinaryHashPayload(sha256_hex=sha)
        elif payload_type is SkippedPayload:
            msg_el = el.find(self._spec.TAG_ERROR)
            msg = msg_el.text if msg_el is not None else ""
            code = el.get(self._spec.ATTR_SKIP_CODE, "unknown")
            try:
                skip_code = SkipCode(code)
            except ValueError:
                skip_code = SkipCode.unknown
            detail = self._parse_detail(el)
            return SkippedPayload(code=skip_code, message=msg, detail=detail)
        elif payload_type is ErrorPayload:
            msg_el = el.find(self._spec.TAG_ERROR)
            msg = msg_el.text if msg_el is not None else ""
            code = el.get(self._spec.ATTR_ERROR_CODE, "unknown")
            try:
                err_code = ErrorCode(code)
            except ValueError:
                err_code = ErrorCode.unknown
            detail = self._parse_detail(el)
            return ErrorPayload(code=err_code, message=msg, detail=detail)
        else:
            raise DeserializationError(f"Unsupported payload type: {payload_type}")

    def _parse_detail(self, el: ET.Element) -> dict[str, object]:
        detail_el = el.find(self._spec.TAG_DETAIL)
        if detail_el is not None and detail_el.text:
            import json
            try:
                return json.loads(detail_el.text)
            except json.JSONDecodeError:
                pass
        return {}