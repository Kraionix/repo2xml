# src/repo2xml/services/serialize/factory.py
from __future__ import annotations

from typing import Dict, Type

from repo2xml.contracts import FormatFactory
from repo2xml.domain.exceptions import SerializationError


class XmlFormatFactory(FormatFactory):
    def create_document_writer(self, **kwargs):
        from repo2xml.services.serialize.xml.document_writer import XMLDocumentWriter
        return XMLDocumentWriter(**kwargs)

    def create_deserializer(self, **kwargs):
        from repo2xml.services.serialize.xml.deserializer import XMLDeserializer
        return XMLDeserializer()


# Registry of format factories keyed by format name.
_FACTORY_REGISTRY: Dict[str, Type[FormatFactory]] = {
    "xml": XmlFormatFactory,
}


def get_format_factory(format_name: str) -> FormatFactory:
    name = format_name.strip().lower()
    cls = _FACTORY_REGISTRY.get(name)
    if cls is None:
        raise SerializationError(f"Unknown format: {name!r}")
    return cls()