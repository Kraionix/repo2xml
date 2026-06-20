# src/repo2xml/services/serialize/xml.py (обновлённый)
from __future__ import annotations

import html
from pathlib import Path
from typing import Optional, Sequence

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
)
from repo2xml.services.serialize.base import BaseSerializer, WriteFn
from repo2xml.services.serialize.xml_utils import (
    cdata,
    esc_attr,
    iso_utc_from_mtime_ns,
    json_detail,
    xml_sanitize_text,
)


class XMLSerializer(BaseSerializer):
    def __init__(
        self,
        *,
        formatting: str = "compact",
        include_mtime: bool = True,
        include_size: bool = True,
        text_decode_errors: str = "replace",
    ):
        super().__init__(formatting=formatting, include_mtime=include_mtime, include_size=include_size)
        self.text_decode_errors = text_decode_errors

    def _register_payload_handlers(self) -> None:
        self.payload_dispatcher.register(MetadataPayload, self._write_metadata)
        self.payload_dispatcher.register(LinkPayload, self._write_link)
        self.payload_dispatcher.register(TextPayload, self._write_text)
        self.payload_dispatcher.register(BinaryHashPayload, self._write_hash)
        self.payload_dispatcher.register(BinaryBase64Payload, self._write_base64)
        self.payload_dispatcher.register(SkippedPayload, self._write_skipped)
        self.payload_dispatcher.register(ErrorPayload, self._write_error)

    def write_header(self, meta: ExportMeta, write: WriteFn) -> None:
        nl = self.nl
        i0 = self.indent(0)
        i1 = self.indent(1)
        i2 = self.indent(2)
        write(f'{i0}<?xml version="1.0" encoding="utf-8"?>{nl}')
        write(
            f'{i0}<repository_context version="{esc_attr(meta.schema_version)}" '
            f'tool_version="{esc_attr(meta.tool_version)}">{nl}'
        )
        write(f"{i1}<meta>{nl}")
        write(f"{i2}<root_path>{html.escape(xml_sanitize_text(meta.root_path))}</root_path>{nl}")
        if meta.generated_at_utc is not None:
            write(
                f"{i2}<generated_at_utc>"
                f"{html.escape(xml_sanitize_text(meta.generated_at_utc))}"
                f"</generated_at_utc>{nl}"
            )
        write(f"{i1}</meta>{nl}")

    def write_footer(self, write: WriteFn) -> None:
        write(f"{self.indent(0)}</repository_context>{self.nl}")

    def write_structure(self, entries: Sequence[FileEntry], write: WriteFn) -> None:
        nl = self.nl
        write(f"{self.indent(1)}<project_structure>{nl}")
        entries_view: Sequence[FileEntry] = entries
        for i in range(len(entries) - 1):
            if entries[i].rel_path > entries[i + 1].rel_path:
                entries_view = sorted(entries, key=lambda e: e.rel_path)
                break
        stack: list[str] = []
        base_level = 2

        def close_to(depth: int) -> None:
            while len(stack) > depth:
                level = base_level + (len(stack) - 1)
                write(f"{self.indent(level)}</dir>{nl}")
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
                    f'{self.indent(level)}<dir name="{esc_attr(dir_parts[j])}" '
                    f'path="{esc_attr(dir_path)}">{nl}'
                )
            file_level = base_level + len(stack)
            write(
                f'{self.indent(file_level)}<file name="{esc_attr(file_name)}" '
                f'path="{esc_attr(rel)}" />{nl}'
            )
        close_to(0)
        write(f"{self.indent(1)}</project_structure>{nl}")

    def write_files_open(self, mode: str, write: WriteFn) -> None:
        write(f'{self.indent(1)}<files mode="{esc_attr(mode)}">{self.nl}')

    def write_files_close(self, write: WriteFn) -> None:
        write(f"{self.indent(1)}</files>{self.nl}")

    def _file_attr_str(self, entry: FileEntry, *, link_target_override: Optional[str] = None) -> str:
        parts: list[str] = [
            f'path="{esc_attr(entry.rel_path)}"',
            f'ext="{esc_attr("".join(Path(entry.rel_path).suffixes))}"',
        ]
        if self.include_size:
            parts.append(f'size="{entry.size}"')
        if self.include_mtime:
            mtime_str = iso_utc_from_mtime_ns(entry.mtime_ns)
            parts.append(f'mtime_utc="{esc_attr(mtime_str)}"')
        if entry.is_symlink:
            parts.append('symlink="true"')
            target = entry.symlink_target or link_target_override
            if target:
                parts.append(f'link_target="{esc_attr(target)}"')
        return " ".join(parts)

    def _write_detail_if_any(self, detail: dict[str, object], *, indent_str: str, write: WriteFn) -> None:
        if not detail:
            return
        write(f"{indent_str}<detail>{cdata(json_detail(detail))}</detail>{self.nl}")

    # ---- Payload handlers ----

    def _write_metadata(self, entry: FileEntry, payload: MetadataPayload, write: WriteFn) -> None:
        attrs = self._file_attr_str(entry)
        write(f'{self.indent(2)}<file {attrs} />{self.nl}')

    def _write_link(self, entry: FileEntry, payload: LinkPayload, write: WriteFn) -> None:
        attrs = self._file_attr_str(entry, link_target_override=payload.link_target)
        write(f'{self.indent(2)}<file {attrs} link_only="true" />{self.nl}')

    def _write_text(self, entry: FileEntry, payload: TextPayload, write: WriteFn) -> None:
        nl = self.nl
        i2 = self.indent(2)
        i3 = self.indent(3)
        attrs = self._file_attr_str(entry)
        content_attrs: list[str] = []
        if payload.encoding:
            content_attrs.append(f' encoding="{esc_attr(payload.encoding)}"')
        if self.text_decode_errors:
            content_attrs.append(f' decode_errors="{esc_attr(self.text_decode_errors)}"')
        write(f'{i2}<file {attrs}>{nl}')
        write(f"{i3}<content{''.join(content_attrs)}>{cdata(payload.text)}</content>{nl}")
        write(f"{i2}</file>{nl}")

    def _write_hash(self, entry: FileEntry, payload: BinaryHashPayload, write: WriteFn) -> None:
        nl = self.nl
        i2 = self.indent(2)
        i3 = self.indent(3)
        attrs = self._file_attr_str(entry)
        write(f'{i2}<file {attrs} binary="true">{nl}')
        write(f'{i3}<content encoding="sha256">{html.escape(payload.sha256_hex)}</content>{nl}')
        write(f"{i2}</file>{nl}")

    def _write_base64(self, entry: FileEntry, payload: BinaryBase64Payload, write: WriteFn) -> None:
        nl = self.nl
        i2 = self.indent(2)
        i3 = self.indent(3)
        attrs = self._file_attr_str(entry)
        write(f'{i2}<file {attrs} binary="true">{nl}')
        write(f'{i3}<content encoding="base64">')
        for chunk in payload.chunks:
            write(chunk)
        write(f"</content>{nl}")
        write(f"{i2}</file>{nl}")

    def _write_skipped(self, entry: FileEntry, payload: SkippedPayload, write: WriteFn) -> None:
        nl = self.nl
        i2 = self.indent(2)
        i3 = self.indent(3)
        attrs = self._file_attr_str(entry)
        write(f'{i2}<file {attrs} skipped="true" skip_code="{esc_attr(payload.code.value)}">{nl}')
        write(f"{i3}<error>{html.escape(xml_sanitize_text(payload.message))}</error>{nl}")
        self._write_detail_if_any(payload.detail, indent_str=i3, write=write)
        write(f"{i2}</file>{nl}")

    def _write_error(self, entry: FileEntry, payload: ErrorPayload, write: WriteFn) -> None:
        nl = self.nl
        i2 = self.indent(2)
        i3 = self.indent(3)
        attrs = self._file_attr_str(entry)
        write(f'{i2}<file {attrs} skipped="true" error_code="{esc_attr(payload.code.value)}">{nl}')
        write(f"{i3}<error>{html.escape(xml_sanitize_text(payload.message))}</error>{nl}")
        self._write_detail_if_any(payload.detail, indent_str=i3, write=write)
        write(f"{i2}</file>{nl}")