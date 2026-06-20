# src/repo2xml/services/serialize/xml.py
from __future__ import annotations

import base64
import html
import json
from datetime import datetime, timezone
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
from repo2xml.services.serialize.base import WriteFn


def _iso_utc_from_mtime_ns(mtime_ns: int) -> str:
    """Convert nanosecond mtime to ISO-8601 UTC timestamp.

    Returns a sentinel string for out-of-range values to avoid a pipeline crash.
    """
    try:
        return datetime.fromtimestamp(mtime_ns / 1_000_000_000, tz=timezone.utc).isoformat()
    except (OverflowError, OSError):
        # Unrepresentable timestamp; use a documented fallback that is still valid ISO-8601.
        return "0001-01-01T00:00:00+00:00"


def _is_valid_xml_char(cp: int) -> bool:
    """
    XML 1.0 valid character ranges:
      - #x9 | #xA | #xD
      - #x20..#xD7FF
      - #xE000..#xFFFD
      - #x10000..#x10FFFF
    """
    return (
        cp == 0x9
        or cp == 0xA
        or cp == 0xD
        or (0x20 <= cp <= 0xD7FF)
        or (0xE000 <= cp <= 0xFFFD)
        or (0x10000 <= cp <= 0x10FFFF)
    )


def _xml_sanitize_text(s: str) -> str:
    """
    Replace characters that are illegal in XML 1.0 with U+FFFD.

    This prevents generating XML documents that fail to parse due to control chars.
    """
    if not s:
        return s
    out: list[str] = []
    changed = False
    for ch in s:
        cp = ord(ch)
        if _is_valid_xml_char(cp):
            out.append(ch)
        else:
            out.append("\uFFFD")
            changed = True
    return "".join(out) if changed else s


def _esc_attr(s: str) -> str:
    """Escape a string for safe use in XML attributes."""
    return html.escape(_xml_sanitize_text(s), quote=True)


def _json_detail(detail: dict[str, object]) -> str:
    """
    Deterministic JSON serialization for detail dictionaries.

    - sort_keys=True for stable output
    - separators to avoid whitespace noise
    - default=str to avoid crashes on unexpected objects
    """
    return json.dumps(detail, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


# CDATA markers are stored in base64 so this source code does not contain
# the CDATA terminator literally (avoids self-rewriting when serializing this repo).
_CDATA_OPEN = base64.b64decode("PCFbQ0RBVEFb").decode("ascii")
_CDATA_CLOSE = base64.b64decode("XV0+").decode("ascii")
_CDATA_SPLIT = base64.b64decode("XV1dXT48IVtDREFUQVs+").decode("ascii")


def _cdata(text: str) -> str:
    """
    Wrap text in a CDATA section.

    If the CDATA close marker appears in content, we split it using the standard
    technique (replace close marker with a safe sequence that closes and reopens CDATA).
    """
    text = _xml_sanitize_text(text)
    text = text.replace(_CDATA_CLOSE, _CDATA_SPLIT)
    return _CDATA_OPEN + text + _CDATA_CLOSE


class XMLSerializer:
    """
    Streaming-friendly XML serializer.

    formatting:
      - "compact" (default): newlines, no indentation
      - "pretty": newlines + TAB indentation
      - "minify": no newlines, no indentation
    """

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

        self.nl = "" if formatting == "minify" else "\n"

    @property
    def supports_structure(self) -> bool:
        return True

    @property
    def supports_files_section(self) -> bool:
        return True

    def _indent(self, level: int) -> str:
        """Indentation policy: tabs only in 'pretty' formatting."""
        if self.formatting == "pretty":
            return "\t" * level
        return ""

    def write_header(self, meta: ExportMeta, write: WriteFn) -> None:
        nl = self.nl
        i0 = self._indent(0)
        i1 = self._indent(1)
        i2 = self._indent(2)

        write(f'{i0}<?xml version="1.0" encoding="utf-8"?>{nl}')
        write(
            f'{i0}<repository_context version="{_esc_attr(meta.schema_version)}" '
            f'tool_version="{_esc_attr(meta.tool_version)}">{nl}'
        )
        write(f"{i1}<meta>{nl}")
        write(f"{i2}<root_path>{html.escape(_xml_sanitize_text(meta.root_path))}</root_path>{nl}")

        if meta.generated_at_utc is not None:
            write(
                f"{i2}<generated_at_utc>"
                f"{html.escape(_xml_sanitize_text(meta.generated_at_utc))}"
                f"</generated_at_utc>{nl}"
            )

        write(f"{i1}</meta>{nl}")

    def write_footer(self, write: WriteFn) -> None:
        write(f"{self._indent(0)}</repository_context>{self.nl}")

    def write_structure(self, entries: Sequence[FileEntry], write: WriteFn) -> None:
        """
        Emit an XML directory tree based on file paths.

        Implementation:
        - Use a stack to open/close <dir> elements without building a full tree object.
        - The pipeline already sorts entries by rel_path for determinism.
          We avoid building a separate list of paths in the common case.
        """
        nl = self.nl
        write(f"{self._indent(1)}<project_structure>{nl}")

        # Defensive fallback: if someone calls the serializer directly with unsorted entries,
        # sort them here. This should not happen in the main pipeline path.
        entries_view: Sequence[FileEntry] = entries
        for i in range(len(entries) - 1):
            if entries[i].rel_path > entries[i + 1].rel_path:
                entries_view = sorted(entries, key=lambda e: e.rel_path)
                break

        stack: list[str] = []
        base_level = 2  # children of <project_structure>

        def close_to(depth: int) -> None:
            while len(stack) > depth:
                level = base_level + (len(stack) - 1)
                write(f"{self._indent(level)}</dir>{nl}")
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
                    f'{self._indent(level)}<dir name="{_esc_attr(dir_parts[j])}" '
                    f'path="{_esc_attr(dir_path)}">{nl}'
                )

            file_level = base_level + len(stack)
            write(
                f'{self._indent(file_level)}<file name="{_esc_attr(file_name)}" '
                f'path="{_esc_attr(rel)}" />{nl}'
            )

        close_to(0)
        write(f"{self._indent(1)}</project_structure>{nl}")

    def write_files_open(self, mode: str, write: WriteFn) -> None:
        write(f'{self._indent(1)}<files mode="{_esc_attr(mode)}">{self.nl}')

    def write_files_close(self, write: WriteFn) -> None:
        write(f"{self._indent(1)}</files>{self.nl}")

    def _file_attr_str(self, entry: FileEntry, *, link_target_override: Optional[str] = None) -> str:
        """
        Build a compact attribute string for a <file> element.

        link_target_override is used for LinkPayload in case the scan did not
        capture a readlink target (platform/permission dependent).
        """
        # Build the attribute list directly, preserving a deterministic order.
        parts: list[str] = [
            f'path="{_esc_attr(entry.rel_path)}"',
            f'ext="{_esc_attr("".join(Path(entry.rel_path).suffixes))}"',
        ]
        if self.include_size:
            parts.append(f'size="{entry.size}"')
        if self.include_mtime:
            mtime_str = _iso_utc_from_mtime_ns(entry.mtime_ns)
            parts.append(f'mtime_utc="{_esc_attr(mtime_str)}"')

        if entry.is_symlink:
            parts.append('symlink="true"')
            target = entry.symlink_target or link_target_override
            if target:
                parts.append(f'link_target="{_esc_attr(target)}"')

        return " ".join(parts)

    def _write_detail_if_any(self, detail: dict[str, object], *, indent: str, write: WriteFn) -> None:
        if not detail:
            return
        # Machine-readable detail for downstream processing.
        write(f"{indent}<detail>{_cdata(_json_detail(detail))}</detail>{self.nl}")

    def write_file(self, entry: FileEntry, payload: FilePayload, write: WriteFn) -> None:
        nl = self.nl
        i2 = self._indent(2)
        i3 = self._indent(3)

        if isinstance(payload, MetadataPayload):
            # Metadata semantics: normal file entry, no <content>, no skipped markers.
            attrs = self._file_attr_str(entry)
            write(f'{i2}<file {attrs} />{nl}')
            return

        if isinstance(payload, LinkPayload):
            # Link-only semantics: normal file entry with link_only marker.
            attrs = self._file_attr_str(entry, link_target_override=payload.link_target)
            write(f'{i2}<file {attrs} link_only="true" />{nl}')
            return

        attrs = self._file_attr_str(entry)

        if isinstance(payload, TextPayload):
            content_attrs: list[str] = []
            if payload.encoding:
                content_attrs.append(f' encoding="{_esc_attr(payload.encoding)}"')
            # Expose decode policy for reproducibility/debugging.
            if self.text_decode_errors:
                content_attrs.append(f' decode_errors="{_esc_attr(self.text_decode_errors)}"')

            write(f'{i2}<file {attrs}>{nl}')
            write(f"{i3}<content{''.join(content_attrs)}>{_cdata(payload.text)}</content>{nl}")
            write(f"{i2}</file>{nl}")
            return

        if isinstance(payload, BinaryHashPayload):
            write(f'{i2}<file {attrs} binary="true">{nl}')
            write(f'{i3}<content encoding="sha256">{html.escape(payload.sha256_hex)}</content>{nl}')
            write(f"{i2}</file>{nl}")
            return

        if isinstance(payload, BinaryBase64Payload):
            write(f'{i2}<file {attrs} binary="true">{nl}')
            write(f'{i3}<content encoding="base64">')
            for chunk in payload.chunks:
                write(chunk)
            write(f"</content>{nl}")
            write(f"{i2}</file>{nl}")
            return

        if isinstance(payload, SkippedPayload):
            write(f'{i2}<file {attrs} skipped="true" skip_code="{_esc_attr(payload.code.value)}">{nl}')
            write(f"{i3}<error>{html.escape(_xml_sanitize_text(payload.message))}</error>{nl}")
            self._write_detail_if_any(payload.detail, indent=i3, write=write)
            write(f"{i2}</file>{nl}")
            return

        if isinstance(payload, ErrorPayload):
            write(f'{i2}<file {attrs} skipped="true" error_code="{_esc_attr(payload.code.value)}">{nl}')
            write(f"{i3}<error>{html.escape(_xml_sanitize_text(payload.message))}</error>{nl}")
            self._write_detail_if_any(payload.detail, indent=i3, write=write)
            write(f"{i2}</file>{nl}")
            return

        write(f'{i2}<file {attrs} skipped="true">{nl}')
        write(f"{i3}<error>Unknown payload</error>{nl}")
        write(f"{i2}</file>{nl}")