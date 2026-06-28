# src/repo2xml/contracts/serialize.py
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import BinaryIO, Set, Type

from repo2xml.contracts.document_writer import DocumentWriter
from repo2xml.domain.model import FilePayload, ParsedRepository


class Deserializer(ABC):
    """Abstract deserialiser for a specific format."""

    @abstractmethod
    def parse(self, stream: BinaryIO, *, strict: bool = False) -> ParsedRepository:
        """Parse the stream into a ParsedRepository."""
        ...

    @classmethod
    def supported_payload_types(cls) -> Set[Type[FilePayload]]:
        return set()


class FormatFactory(ABC):
    """Creates a DocumentWriter / Deserializer pair for a given format."""

    @abstractmethod
    def create_document_writer(self, **kwargs) -> DocumentWriter:
        """Create a DocumentWriter instance for the format."""
        ...

    @abstractmethod
    def create_deserializer(self, **kwargs) -> Deserializer:
        """Create a Deserializer instance."""
        ...

    @classmethod
    def supported_payload_types(cls) -> Set[Type[FilePayload]]:
        return set()