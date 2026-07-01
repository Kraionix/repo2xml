# src/repo2xml/services/serialize/xml/document_writer.py
from __future__ import annotations

import html
from pathlib import Path
from typing import List, Optional, Sequence

from repo2xml.contracts.document_writer import DocumentWriter
from repo2xml.domain.constants import SCHEMA_VERSION
from repo2xml.domain.model import (
    BinaryBase64Payload,
    BinaryHashPayload,
    ErrorPayload,
    ExportMeta,
    FileEntry,
    FilePayload,
    LinkPayload,
    MetadataPayload,
    SkippedPayload,
    TextPayload,
    TokenStats,
)
from repo2xml.services.serialize.base import WriteFn
from repo2xml.services.serialize.xml.format_spec import XmlFormatSpec
from repo2xml.services.serialize.xml_utils import (
    cdata,
    esc_attr,
    iso_utc_from_mtime_ns,
    json_detail,
    xml_sanitize_text,
)


class XMLDocumentWriter(DocumentWriter):
    """
    XML implementation of DocumentWriter.

    Produces the repo2xml XML format (schema version 1.2).
    Supports compact, pretty, and minified output.
    Now parameterized with root tag and optional structure inclusion.
    """

    def __init__(
        self,
        *,
        root_tag: str = XmlFormatSpec.TAG_ROOT,
        include_structure: bool = True,
        formatting: str = "compact",
        include_mtime: bool = True,
        include_size: bool = True,
        text_decode_errors: str = "replace",
        write_fn: WriteFn,
    ):
        if formatting not in {"compact", "pretty", "minify"}:
            raise ValueError(f"Unknown formatting: {formatting}")
        self.root_tag = root_tag
        self.include_structure = include_structure
        self.formatting = formatting
        self.include_mtime = include_mtime
        self.include_size = include_size
        self.text_decode_errors = text_decode_errors
        self._write = write_fn

        # State to track whether we are inside the files section
        self._files_section_open = False

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @property
    def nl(self) -> str:
        return "" if self.formatting == "minify" else "\n"

    def indent(self, level: int) -> str:
        return "\t" * level if self.formatting == "pretty" else ""

    def _file_attr_str(self, entry: FileEntry, *, link_target_override: Optional[str] = None) -> str:
        parts = [
            f'path="{esc_attr(entry.rel_path)}"',
            f'ext="{esc_attr("".join(Path(entry.rel_path).suffixes))}"',
        ]
        if self.include_size:
            parts.append(f'size="{entry.size}"')
        if self.include_mtime:
            parts.append(f'mtime_utc="{esc_attr(iso_utc_from_mtime_ns(entry.mtime_ns))}"')
        if entry.is_symlink:
            parts.append('symlink="true"')
            target = entry.symlink_target or link_target_override
            if target:
                parts.append(f'link_target="{esc_attr(target)}"')
        return " ".join(parts)

    def _write_detail_if_any(self, detail: dict[str, object], *, indent_str: str) -> None:
        if not detail:
            return
        self._write(f"{indent_str}<{XmlFormatSpec.TAG_DETAIL}>{cdata(json_detail(detail))}</{XmlFormatSpec.TAG_DETAIL}>{self.nl}")

    # ------------------------------------------------------------------
    # DocumentWriter implementation
    # ------------------------------------------------------------------

    def begin_document(self, meta: ExportMeta) -> None:
        nl = self.nl
        i0 = self.indent(0)
        i1 = self.indent(1)
        i2 = self.indent(2)
        self._write(f'{i0}<?xml version="1.0" encoding="utf-8"?>{nl}')
        self._write(
            f'{i0}<{self.root_tag} {XmlFormatSpec.ATTR_VERSION}="{SCHEMA_VERSION}" '
            f'{XmlFormatSpec.ATTR_TOOL_VERSION}="{esc_attr(meta.tool_version)}">{nl}'
        )
        self._write(f"{i1}<{XmlFormatSpec.TAG_META}>{nl}")
        self._write(f"{i2}<{XmlFormatSpec.TAG_ROOT_PATH}>{html.escape(xml_sanitize_text(meta.root_path))}</{XmlFormatSpec.TAG_ROOT_PATH}>{nl}")
        if meta.generated_at_utc is not None:
            self._write(
                f"{i2}<{XmlFormatSpec.TAG_GENERATED_AT}>"
                f"{html.escape(xml_sanitize_text(meta.generated_at_utc))}"
                f"</{XmlFormatSpec.TAG_GENERATED_AT}>{nl}"
            )
        self._write(f"{i1}</{XmlFormatSpec.TAG_META}>{nl}")

    def write_structure(self, entries: List[FileEntry]) -> None:
        if not self.include_structure:
            return
        nl = self.nl
        self._write(f"{self.indent(1)}<{XmlFormatSpec.TAG_PROJECT_STRUCTURE}>{nl}")
        entries_view = sorted(entries, key=lambda e: e.rel_path)
        stack: list[str] = []
        base_level = 2

        def close_to(depth: int) -> None:
            while len(stack) > depth:
                level = base_level + (len(stack) - 1)
                self._write(f"{self.indent(level)}</{XmlFormatSpec.TAG_DIR}>{nl}")
                stack.pop()

        for entry in entries_view:
            rel = entry.rel_path
            parts = rel.split("/")
            dir_parts, file_name = parts[:-1], parts[-1]
            common = 0
            max_common = min(len(stack), len(dir_parts))
            while common < max_common and stack[common] == dir_parts[common]:
                common += 1
            close_to(common)
            for j in range(common, len(dir_parts)):
                stack.append(dir_parts[j])
                dir_path = "/".join(stack)
                level = base_level + (len(stack) - 1)
                self._write(
                    f'{self.indent(level)}<{XmlFormatSpec.TAG_DIR} {XmlFormatSpec.ATTR_NAME}="{esc_attr(dir_parts[j])}" '
                    f'{XmlFormatSpec.ATTR_PATH}="{esc_attr(dir_path)}">{nl}'
                )
            file_level = base_level + len(stack)
            self._write(
                f'{self.indent(file_level)}<{XmlFormatSpec.TAG_FILE} {XmlFormatSpec.ATTR_NAME}="{esc_attr(file_name)}" '
                f'{XmlFormatSpec.ATTR_PATH}="{esc_attr(rel)}" />{nl}'
            )
        close_to(0)
        self._write(f"{self.indent(1)}</{XmlFormatSpec.TAG_PROJECT_STRUCTURE}>{nl}")

    def begin_files_section(self, mode: str) -> None:
        self._write(f'{self.indent(1)}<{XmlFormatSpec.TAG_FILES} {XmlFormatSpec.ATTR_MODE}="{esc_attr(mode)}">{self.nl}')
        self._files_section_open = True

    def write_file(self, entry: FileEntry, payload: FilePayload, token_count: Optional[int] = None) -> None:
        # Delegate to private writers based on payload type
        if isinstance(payload, MetadataPayload):
            self._write_metadata(entry, payload, token_count)
        elif isinstance(payload, TextPayload):
            self._write_text(entry, payload, token_count)
        elif isinstance(payload, BinaryBase64Payload):
            self._write_binary_base64(entry, payload, token_count)
        elif isinstance(payload, BinaryHashPayload):
            self._write_binary_hash(entry, payload, token_count)
        elif isinstance(payload, LinkPayload):
            self._write_link(entry, payload, token_count)
        elif isinstance(payload, SkippedPayload):
            self._write_skipped(entry, payload, token_count)
        elif isinstance(payload, ErrorPayload):
            self._write_error(entry, payload, token_count)
        else:
            raise AssertionError(f"Unhandled payload type: {type(payload)}")

    def end_files_section(self) -> None:
        self._write(f"{self.indent(1)}</{XmlFormatSpec.TAG_FILES}>{self.nl}")
        self._files_section_open = False

    def write_statistics(self, stats: Optional[TokenStats]) -> None:
        if stats is None or stats.total_tokens == 0:
            return
        self._write(f'{self.indent(1)}<{XmlFormatSpec.TAG_STATISTICS} {XmlFormatSpec.ATTR_TOTAL_TOKENS}="{stats.total_tokens}" />{self.nl}')

    def end_document(self) -> None:
        self._write(f"{self.indent(0)}</{self.root_tag}>{self.nl}")

    # ------------------------------------------------------------------
    # Private payload writers
    # ------------------------------------------------------------------

    def _write_metadata(self, entry: FileEntry, payload: MetadataPayload, token_count: Optional[int] = None) -> None:
        attrs = self._file_attr_str(entry)
        self._write(f'{self.indent(2)}<{XmlFormatSpec.TAG_FILE} {attrs} />{self.nl}')

    def _write_text(self, entry: FileEntry, payload: TextPayload, token_count: Optional[int] = None) -> None:
        nl = self.nl
        i2 = self.indent(2)
        i3 = self.indent(3)
        attrs = self._file_attr_str(entry)
        if token_count is not None:
            attrs += f' tokens="{token_count}"'
        content_attrs = []
        if payload.encoding:
            content_attrs.append(f' {XmlFormatSpec.ATTR_ENCODING}="{esc_attr(payload.encoding)}"')
        if self.text_decode_errors:
            content_attrs.append(f' {XmlFormatSpec.ATTR_DECODE_ERRORS}="{esc_attr(self.text_decode_errors)}"')
        self._write(f'{i2}<{XmlFormatSpec.TAG_FILE} {attrs}>{nl}')
        self._write(f"{i3}<{XmlFormatSpec.TAG_CONTENT}{''.join(content_attrs)}>{cdata(payload.text)}</{XmlFormatSpec.TAG_CONTENT}>{nl}")
        self._write(f"{i2}</{XmlFormatSpec.TAG_FILE}>{nl}")

    def _write_binary_base64(self, entry: FileEntry, payload: BinaryBase64Payload, token_count: Optional[int] = None) -> None:
        nl = self.nl
        i2 = self.indent(2)
        i3 = self.indent(3)
        attrs = self._file_attr_str(entry)
        self._write(f'{i2}<{XmlFormatSpec.TAG_FILE} {attrs} {XmlFormatSpec.ATTR_BINARY}="true">{nl}')
        self._write(f'{i3}<{XmlFormatSpec.TAG_CONTENT} {XmlFormatSpec.ATTR_ENCODING}="base64">')
        for chunk in payload.chunks:
            self._write(chunk)
        self._write(f"</{XmlFormatSpec.TAG_CONTENT}>{nl}")
        self._write(f"{i2}</{XmlFormatSpec.TAG_FILE}>{nl}")

    def _write_binary_hash(self, entry: FileEntry, payload: BinaryHashPayload, token_count: Optional[int] = None) -> None:
        nl = self.nl
        i2 = self.indent(2)
        i3 = self.indent(3)
        attrs = self._file_attr_str(entry)
        self._write(f'{i2}<{XmlFormatSpec.TAG_FILE} {attrs} {XmlFormatSpec.ATTR_BINARY}="true">{nl}')
        self._write(f'{i3}<{XmlFormatSpec.TAG_CONTENT} {XmlFormatSpec.ATTR_ENCODING}="sha256">{html.escape(payload.sha256_hex)}</{XmlFormatSpec.TAG_CONTENT}>{nl}')
        self._write(f"{i2}</{XmlFormatSpec.TAG_FILE}>{nl}")

    def _write_link(self, entry: FileEntry, payload: LinkPayload, token_count: Optional[int] = None) -> None:
        attrs = self._file_attr_str(entry, link_target_override=payload.link_target)
        self._write(f'{self.indent(2)}<{XmlFormatSpec.TAG_FILE} {attrs} {XmlFormatSpec.ATTR_LINK_ONLY}="true" />{self.nl}')

    def _write_skipped(self, entry: FileEntry, payload: SkippedPayload, token_count: Optional[int] = None) -> None:
        nl = self.nl
        i2 = self.indent(2)
        i3 = self.indent(3)
        attrs = self._file_attr_str(entry)
        self._write(f'{i2}<{XmlFormatSpec.TAG_FILE} {attrs} {XmlFormatSpec.ATTR_SKIPPED}="true" {XmlFormatSpec.ATTR_SKIP_CODE}="{esc_attr(payload.code.value)}">{nl}')
        self._write(f"{i3}<{XmlFormatSpec.TAG_ERROR}>{html.escape(xml_sanitize_text(payload.message))}</{XmlFormatSpec.TAG_ERROR}>{nl}")
        self._write_detail_if_any(payload.detail, indent_str=i3)
        self._write(f"{i2}</{XmlFormatSpec.TAG_FILE}>{nl}")

    def _write_error(self, entry: FileEntry, payload: ErrorPayload, token_count: Optional[int] = None) -> None:
        nl = self.nl
        i2 = self.indent(2)
        i3 = self.indent(3)
        attrs = self._file_attr_str(entry)
        self._write(f'{i2}<{XmlFormatSpec.TAG_FILE} {attrs} {XmlFormatSpec.ATTR_SKIPPED}="true" {XmlFormatSpec.ATTR_ERROR_CODE}="{esc_attr(payload.code.value)}">{nl}')
        self._write(f"{i3}<{XmlFormatSpec.TAG_ERROR}>{html.escape(xml_sanitize_text(payload.message))}</{XmlFormatSpec.TAG_ERROR}>{nl}")
        self._write_detail_if_any(payload.detail, indent_str=i3)
        self._write(f"{i2}</{XmlFormatSpec.TAG_FILE}>{nl}")

    def set_write_fn(self, write_fn: WriteFn) -> None:
        self._write = write_fn