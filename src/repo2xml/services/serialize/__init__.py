# src/repo2xml/services/serialize/__init__.py
"""Serialization subsystem (format-specific writers)."""

from repo2xml.services.serialize.xml.document_writer import XMLDocumentWriter
from repo2xml.services.serialize.xml.deserializer import XMLDeserializer

__all__ = [
    "XMLDocumentWriter",
    "XMLDeserializer",
]