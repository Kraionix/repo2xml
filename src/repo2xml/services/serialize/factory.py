# src/repo2xml/services/serialize/factory.py
from __future__ import annotations

from typing import Dict, Type

from repo2xml.contracts import FormatFactory
from repo2xml.domain.exceptions import SerializationError


class XmlFormatFactory(FormatFactory):
    def create_serializer(self, **kwargs) -> 'Serializer':
        from repo2xml.services.serialize.xml.serializer import XMLSerializer
        return XMLSerializer(**kwargs)

    def create_deserializer(self, **kwargs) -> 'Deserializer':
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