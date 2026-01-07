from __future__ import annotations

import base64
import html
from datetime import datetime, timezone
from pathlib import Path
from typing import List

from ..core.domain import FileNode


def _esc_attr(s: str) -> str:
    """Escape a string for safe use in XML attributes."""
    return html.escape(s, quote=True)


# CDATA markers are stored in base64 so this source code does not contain
# the CDATA terminator literally (avoids self-rewriting when serializing this repo).
#
# Human-readable equivalents (spaced out intentionally):
# - open: "< ! [ C D A T A ["
# - close: "] ] >"
# - split: "] ] ] ] > < ! [ C D A T A [ >"
_CDATA_OPEN = base64.b64decode("PCFbQ0RBVEFb").decode("ascii")
_CDATA_CLOSE = base64.b64decode("XV0+").decode("ascii")
_CDATA_SPLIT = base64.b64decode("XV1dXT48IVtDREFUQVs+").decode("ascii")


def _cdata(text: str) -> str:
    """
    Wrap text in a CDATA section.

    If the CDATA close marker appears in content, we split it using the standard
    technique (replace close marker with a safe sequence that closes and reopens CDATA).
    """
    # One-pass replace (no extra membership scan).
    text = text.replace(_CDATA_CLOSE, _CDATA_SPLIT)
    return _CDATA_OPEN + text + _CDATA_CLOSE


def _iso_utc_from_mtime_ns(mtime_ns: int) -> str:
    """Convert nanosecond mtime to ISO-8601 UTC timestamp."""
    return datetime.fromtimestamp(mtime_ns / 1_000_000_000, tz=timezone.utc).isoformat()


class XMLSerializer:
    """
    Streaming-ish XML serializer.

    formatting:
      - "compact" (default): newlines, no indentation
      - "pretty": newlines + TAB indentation
      - "minify": no newlines, no indentation
    """

    def __init__(
        self,
        root_path_str: str,
        generated_at_utc: str,
        tool_version: str = "0.1.0",
        formatting: str = "compact",
    ):
        if formatting not in {"compact", "pretty", "minify"}:
            raise ValueError(f"Unknown formatting: {formatting}")

        self.root_path = root_path_str
        self.generated_at_utc = generated_at_utc
        self.tool_version = tool_version
        self.formatting = formatting

        # Newline policy:
        # - compact/pretty => one XML tag per line (readable, stable diffs)
        # - minify => zero newlines
        self.nl = "" if formatting == "minify" else "\n"

    def _indent(self, level: int) -> str:
        """Indentation policy: tabs only in 'pretty' formatting."""
        if self.formatting == "pretty":
            return "\t" * level
        return ""

    def stream_header(self) -> str:
        nl = self.nl
        i0 = self._indent(0)
        i1 = self._indent(1)
        i2 = self._indent(2)

        return (
            f'{i0}<?xml version="1.0" encoding="utf-8"?>{nl}'
            f'{i0}<repository_context version="1.0" tool_version="{_esc_attr(self.tool_version)}">{nl}'
            f"{i1}<meta>{nl}"
            f"{i2}<root_path>{html.escape(self.root_path)}</root_path>{nl}"
            f"{i2}<generated_at_utc>{html.escape(self.generated_at_utc)}</generated_at_utc>{nl}"
            f"{i1}</meta>{nl}"
        )

    def stream_footer(self) -> str:
        return f"{self._indent(0)}</repository_context>{self.nl}"

    def project_structure_xml(self, nodes: List[FileNode]) -> str:
        """
        Emit an XML directory tree based on file paths.

        Implementation:
        - Sort all relative paths.
        - Use a stack to open/close <dir> elements without building a full tree object.
        """
        nl = self.nl
        out: list[str] = [f"{self._indent(1)}<project_structure>{nl}"]

        paths = sorted(n.rel_path for n in nodes)
        stack: list[str] = []
        base_level = 2  # children of <project_structure>

        def close_to(depth: int) -> None:
            while len(stack) > depth:
                level = base_level + (len(stack) - 1)
                out.append(f"{self._indent(level)}</dir>{nl}")
                stack.pop()

        for rel in paths:
            parts = rel.split("/")
            dir_parts, file_name = parts[:-1], parts[-1]

            # Find common prefix depth between current stack and this file's dir path.
            common = 0
            max_common = min(len(stack), len(dir_parts))
            while common < max_common and stack[common] == dir_parts[common]:
                common += 1

            close_to(common)

            # Open new directories.
            for i in range(common, len(dir_parts)):
                stack.append(dir_parts[i])
                dir_path = "/".join(stack)
                level = base_level + (len(stack) - 1)
                out.append(
                    f'{self._indent(level)}<dir name="{_esc_attr(dir_parts[i])}" path="{_esc_attr(dir_path)}">{nl}'
                )

            # Emit file node.
            file_level = base_level + len(stack)
            out.append(
                f'{self._indent(file_level)}<file name="{_esc_attr(file_name)}" path="{_esc_attr(rel)}" />{nl}'
            )

        close_to(0)
        out.append(f"{self._indent(1)}</project_structure>{nl}")
        return "".join(out)

    def files_open(self, mode: str) -> str:
        """Open the <files> section."""
        return f'{self._indent(1)}<files mode="{_esc_attr(mode)}">{self.nl}'

    def files_close(self) -> str:
        """Close the <files> section."""
        return f"{self._indent(1)}</files>{self.nl}"

    def _file_attr_str(self, node: FileNode) -> str:
        """
        Build a compact attribute string for a <file> element.
        """
        attrs = {
            "path": node.rel_path,
            "size": str(node.size),
            "ext": "".join(Path(node.rel_path).suffixes),
            "mtime_utc": _iso_utc_from_mtime_ns(node.mtime_ns),
        }
        parts = [f'{k}="{_esc_attr(v)}"' for k, v in attrs.items()]
        if node.is_symlink:
            parts.append('symlink="true"')
            if node.symlink_target:
                parts.append(f'link_target="{_esc_attr(node.symlink_target)}"')
        return " ".join(parts)

    def serialize_metadata(self, node: FileNode) -> str:
        """Emit a self-closing file entry (metadata only)."""
        return f'{self._indent(2)}<file {self._file_attr_str(node)} />{self.nl}'

    def serialize_link(self, node: FileNode) -> str:
        """Emit a link-only entry for symlinks when symlink mode is 'as-link'."""
        return f'{self._indent(2)}<file {self._file_attr_str(node)} link_only="true" />{self.nl}'

    def serialize_text(self, node: FileNode, content: str) -> str:
        """Emit a file entry with text content wrapped in CDATA."""
        nl = self.nl
        return (
            f'{self._indent(2)}<file {self._file_attr_str(node)}>{nl}'
            f"{self._indent(3)}<content>{_cdata(content)}</content>{nl}"
            f"{self._indent(2)}</file>{nl}"
        )

    def serialize_binary_base64(self, node: FileNode, b64: str) -> str:
        """Emit binary content as base64 text."""
        nl = self.nl
        return (
            f'{self._indent(2)}<file {self._file_attr_str(node)} binary="true">{nl}'
            f'{self._indent(3)}<content encoding="base64">{b64}</content>{nl}'
            f"{self._indent(2)}</file>{nl}"
        )

    def serialize_binary_hash(self, node: FileNode, sha256_hex: str) -> str:
        """Emit a SHA-256 digest for binary content instead of embedding bytes."""
        nl = self.nl
        return (
            f'{self._indent(2)}<file {self._file_attr_str(node)} binary="true">{nl}'
            f'{self._indent(3)}<content encoding="sha256">{sha256_hex}</content>{nl}'
            f"{self._indent(2)}</file>{nl}"
        )

    def serialize_error(self, node: FileNode, error: str) -> str:
        """Emit a skipped/error entry with a human-readable reason."""
        nl = self.nl
        return (
            f'{self._indent(2)}<file path="{_esc_attr(node.rel_path)}" skipped="true">{nl}'
            f"{self._indent(3)}<error>{html.escape(error)}</error>{nl}"
            f"{self._indent(2)}</file>{nl}"
        )