# src/repo2xml/contracts/serialize.py
from __future__ import annotations

from typing import BinaryIO, Protocol, Set, Type

from repo2xml.contracts.document_writer import DocumentWriter
from repo2xml.domain.model import FilePayload, ParsedRepository


class Deserializer(Protocol):
    """Abstract deserialiser for a specific format."""

    def parse(self, stream: BinaryIO, *, strict: bool = False) -> ParsedRepository:
        """Parse the stream into a ParsedRepository."""
        ...

    @classmethod
    def supported_payload_types(cls) -> Set[Type[FilePayload]]:
        return set()


class FormatFactory(Protocol):
    """Creates a DocumentWriter / Deserializer pair for a given format."""

    def create_document_writer(self, **kwargs) -> DocumentWriter:
        """Create a DocumentWriter instance for the format."""
        ...

    def create_deserializer(self, **kwargs) -> Deserializer:
        """Create a Deserializer instance."""
        ...

    @classmethod
    def supported_payload_types(cls) -> Set[Type[FilePayload]]:
        return set()