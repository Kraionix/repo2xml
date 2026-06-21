# src/repo2xml/services/serialize/xml/serializer.py
from __future__ import annotations

import html
from pathlib import Path
from typing import List, Optional, Sequence

from repo2xml.application.contracts import Serializer
from repo2xml.domain.model import (
    BinaryBase64Payload,
    BinaryHashPayload,
    ErrorPayload,
    ExportMeta,
    FileEntry,
    LinkPayload,
    MetadataPayload,
    SkippedPayload,
    TextPayload,
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


class XMLSerializer(Serializer):
    def __init__(
        self,
        *,
        formatting: str = "compact",
        include_mtime: bool = True,
        include_size: bool = True,
        text_decode_errors: str = "replace",
    ):
        if formatting not in {"compact", "pretty", "minify"}:
            raise ValueError(f"Unknown formatting: {formatting}")
        self.formatting = formatting
        self.include_mtime = include_mtime
        self.include_size = include_size
        self.text_decode_errors = text_decode_errors

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

    def _write_detail_if_any(self, detail: dict[str, object], *, indent_str: str, write: WriteFn) -> None:
        if not detail:
            return
        write(f"{indent_str}<{XmlFormatSpec.TAG_DETAIL}>{cdata(json_detail(detail))}</{XmlFormatSpec.TAG_DETAIL}>{self.nl}")

    # ------------------------------------------------------------------
    # High-level structure
    # ------------------------------------------------------------------

    def write_header(self, meta: ExportMeta, write: WriteFn) -> None:
        nl = self.nl
        i0 = self.indent(0)
        i1 = self.indent(1)
        i2 = self.indent(2)
        write(f'{i0}<?xml version="1.0" encoding="utf-8"?>{nl}')
        write(
            f'{i0}<{XmlFormatSpec.TAG_ROOT} {XmlFormatSpec.ATTR_VERSION}="{esc_attr(meta.schema_version)}" '
            f'{XmlFormatSpec.ATTR_TOOL_VERSION}="{esc_attr(meta.tool_version)}">{nl}'
        )
        write(f"{i1}<{XmlFormatSpec.TAG_META}>{nl}")
        write(f"{i2}<{XmlFormatSpec.TAG_ROOT_PATH}>{html.escape(xml_sanitize_text(meta.root_path))}</{XmlFormatSpec.TAG_ROOT_PATH}>{nl}")
        if meta.generated_at_utc is not None:
            write(
                f"{i2}<{XmlFormatSpec.TAG_GENERATED_AT}>"
                f"{html.escape(xml_sanitize_text(meta.generated_at_utc))}"
                f"</{XmlFormatSpec.TAG_GENERATED_AT}>{nl}"
            )
        write(f"{i1}</{XmlFormatSpec.TAG_META}>{nl}")

    def write_footer(self, write: WriteFn) -> None:
        write(f"{self.indent(0)}</{XmlFormatSpec.TAG_ROOT}>{self.nl}")

    def write_structure(self, entries: List[FileEntry], write: WriteFn) -> None:
        nl = self.nl
        write(f"{self.indent(1)}<{XmlFormatSpec.TAG_PROJECT_STRUCTURE}>{nl}")
        entries_view = sorted(entries, key=lambda e: e.rel_path)
        stack: list[str] = []
        base_level = 2

        def close_to(depth: int) -> None:
            while len(stack) > depth:
                level = base_level + (len(stack) - 1)
                write(f"{self.indent(level)}</{XmlFormatSpec.TAG_DIR}>{nl}")
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
                write(
                    f'{self.indent(level)}<{XmlFormatSpec.TAG_DIR} {XmlFormatSpec.ATTR_NAME}="{esc_attr(dir_parts[j])}" '
                    f'{XmlFormatSpec.ATTR_PATH}="{esc_attr(dir_path)}">{nl}'
                )
            file_level = base_level + len(stack)
            write(
                f'{self.indent(file_level)}<{XmlFormatSpec.TAG_FILE} {XmlFormatSpec.ATTR_NAME}="{esc_attr(file_name)}" '
                f'{XmlFormatSpec.ATTR_PATH}="{esc_attr(rel)}" />{nl}'
            )
        close_to(0)
        write(f"{self.indent(1)}</{XmlFormatSpec.TAG_PROJECT_STRUCTURE}>{nl}")

    def write_files_open(self, mode: str, write: WriteFn) -> None:
        write(f'{self.indent(1)}<{XmlFormatSpec.TAG_FILES} {XmlFormatSpec.ATTR_MODE}="{esc_attr(mode)}">{self.nl}')

    def write_files_close(self, write: WriteFn) -> None:
        write(f"{self.indent(1)}</{XmlFormatSpec.TAG_FILES}>{self.nl}")

    # ------------------------------------------------------------------
    # Payload writers (one per type)
    # ------------------------------------------------------------------

    def write_metadata(self, entry: FileEntry, payload: MetadataPayload, write: WriteFn) -> None:
        attrs = self._file_attr_str(entry)
        write(f'{self.indent(2)}<{XmlFormatSpec.TAG_FILE} {attrs} />{self.nl}')

    def write_text(self, entry: FileEntry, payload: TextPayload, write: WriteFn) -> None:
        nl = self.nl
        i2 = self.indent(2)
        i3 = self.indent(3)
        attrs = self._file_attr_str(entry)
        content_attrs = []
        if payload.encoding:
            content_attrs.append(f' {XmlFormatSpec.ATTR_ENCODING}="{esc_attr(payload.encoding)}"')
        if self.text_decode_errors:
            content_attrs.append(f' {XmlFormatSpec.ATTR_DECODE_ERRORS}="{esc_attr(self.text_decode_errors)}"')
        write(f'{i2}<{XmlFormatSpec.TAG_FILE} {attrs}>{nl}')
        write(f"{i3}<{XmlFormatSpec.TAG_CONTENT}{''.join(content_attrs)}>{cdata(payload.text)}</{XmlFormatSpec.TAG_CONTENT}>{nl}")
        write(f"{i2}</{XmlFormatSpec.TAG_FILE}>{nl}")

    def write_binary_base64(self, entry: FileEntry, payload: BinaryBase64Payload, write: WriteFn) -> None:
        nl = self.nl
        i2 = self.indent(2)
        i3 = self.indent(3)
        attrs = self._file_attr_str(entry)
        write(f'{i2}<{XmlFormatSpec.TAG_FILE} {attrs} {XmlFormatSpec.ATTR_BINARY}="true">{nl}')
        write(f'{i3}<{XmlFormatSpec.TAG_CONTENT} {XmlFormatSpec.ATTR_ENCODING}="base64">')
        for chunk in payload.chunks:
            write(chunk)
        write(f"</{XmlFormatSpec.TAG_CONTENT}>{nl}")
        write(f"{i2}</{XmlFormatSpec.TAG_FILE}>{nl}")

    def write_binary_hash(self, entry: FileEntry, payload: BinaryHashPayload, write: WriteFn) -> None:
        nl = self.nl
        i2 = self.indent(2)
        i3 = self.indent(3)
        attrs = self._file_attr_str(entry)
        write(f'{i2}<{XmlFormatSpec.TAG_FILE} {attrs} {XmlFormatSpec.ATTR_BINARY}="true">{nl}')
        write(f'{i3}<{XmlFormatSpec.TAG_CONTENT} {XmlFormatSpec.ATTR_ENCODING}="sha256">{html.escape(payload.sha256_hex)}</{XmlFormatSpec.TAG_CONTENT}>{nl}')
        write(f"{i2}</{XmlFormatSpec.TAG_FILE}>{nl}")

    def write_link(self, entry: FileEntry, payload: LinkPayload, write: WriteFn) -> None:
        attrs = self._file_attr_str(entry, link_target_override=payload.link_target)
        write(f'{self.indent(2)}<{XmlFormatSpec.TAG_FILE} {attrs} {XmlFormatSpec.ATTR_LINK_ONLY}="true" />{self.nl}')

    def write_skipped(self, entry: FileEntry, payload: SkippedPayload, write: WriteFn) -> None:
        nl = self.nl
        i2 = self.indent(2)
        i3 = self.indent(3)
        attrs = self._file_attr_str(entry)
        write(f'{i2}<{XmlFormatSpec.TAG_FILE} {attrs} {XmlFormatSpec.ATTR_SKIPPED}="true" {XmlFormatSpec.ATTR_SKIP_CODE}="{esc_attr(payload.code.value)}">{nl}')
        write(f"{i3}<{XmlFormatSpec.TAG_ERROR}>{html.escape(xml_sanitize_text(payload.message))}</{XmlFormatSpec.TAG_ERROR}>{nl}")
        self._write_detail_if_any(payload.detail, indent_str=i3, write=write)
        write(f"{i2}</{XmlFormatSpec.TAG_FILE}>{nl}")

    def write_error(self, entry: FileEntry, payload: ErrorPayload, write: WriteFn) -> None:
        nl = self.nl
        i2 = self.indent(2)
        i3 = self.indent(3)
        attrs = self._file_attr_str(entry)
        write(f'{i2}<{XmlFormatSpec.TAG_FILE} {attrs} {XmlFormatSpec.ATTR_SKIPPED}="true" {XmlFormatSpec.ATTR_ERROR_CODE}="{esc_attr(payload.code.value)}">{nl}')
        write(f"{i3}<{XmlFormatSpec.TAG_ERROR}>{html.escape(xml_sanitize_text(payload.message))}</{XmlFormatSpec.TAG_ERROR}>{nl}")
        self._write_detail_if_any(payload.detail, indent_str=i3, write=write)
        write(f"{i2}</{XmlFormatSpec.TAG_FILE}>{nl}")