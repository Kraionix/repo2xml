# src/repo2xml/application/partition/buffer_manager.py
from __future__ import annotations

import io
from dataclasses import dataclass
from typing import List, Optional

from repo2xml.contracts import DocumentWriter, TokenCounter
from repo2xml.domain.model import FileEntry, FilePayload


@dataclass(slots=True)
class BufferItem:
    """A single file entry buffered for a part."""
    file_xml: str                # serialized <file> element
    entry: FileEntry
    payload: FilePayload         # the actual payload (to be used when flushing)
    original_token_count: int    # tokens in the file content (from TokenCountStep)
    xml_tokens: int              # tokens in the serialized XML string (including wrapper)


class BufferManager:
    """
    Manages the buffer of file entries for the current part.
    """

    def __init__(
        self,
        max_tokens: int,
        token_counter: TokenCounter,
        document_writer: DocumentWriter,
    ) -> None:
        self._max_tokens = max_tokens
        self._token_counter = token_counter
        self._document_writer = document_writer
        self._buffer: List[BufferItem] = []
        self._current_tokens: int = 0

    def add_file(self, entry: FileEntry, payload: FilePayload, original_token_count: int) -> None:
        """
        Serialize the file to XML, count tokens in the XML, and add to buffer.
        """
        # Serialize the file to a string using the document writer with a temporary StringIO
        output = io.StringIO()
        def write_fn(s: str) -> None:
            output.write(s)

        # Save current write_fn and temporarily replace it
        original_write_fn = self._document_writer._write
        self._document_writer.set_write_fn(write_fn)

        try:
            self._document_writer.write_file(entry, payload, original_token_count)
        finally:
            self._document_writer.set_write_fn(original_write_fn)

        file_xml = output.getvalue()
        output.close()

        # Count tokens in the XML representation
        xml_tokens = self._token_counter.count(file_xml)

        item = BufferItem(
            file_xml=file_xml,
            entry=entry,
            payload=payload,
            original_token_count=original_token_count,
            xml_tokens=xml_tokens,
        )
        self._buffer.append(item)
        self._current_tokens += xml_tokens

    def rollback_last(self) -> Optional[BufferItem]:
        """
        Remove the last added file from the buffer and return it.
        Returns None if buffer is empty.
        """
        if not self._buffer:
            return None
        item = self._buffer.pop()
        self._current_tokens -= item.xml_tokens
        return item

    def is_over_limit(self) -> bool:
        """Return True if the total token count in the buffer exceeds the limit."""
        return self._current_tokens > self._max_tokens

    def flush_buffer(self) -> List[BufferItem]:
        """Return all items and clear the buffer."""
        items = self._buffer[:]
        self._buffer.clear()
        self._current_tokens = 0
        return items

    def get_current_tokens(self) -> int:
        return self._current_tokens

    def get_file_count(self) -> int:
        return len(self._buffer)

    def is_empty(self) -> bool:
        return len(self._buffer) == 0