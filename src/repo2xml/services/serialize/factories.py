from __future__ import annotations

from repo2xml.services.serialize.base import Serializer
from repo2xml.services.serialize.xml import XMLSerializer


def create_serializer(*, fmt: str, formatting: str) -> Serializer:
    """
    Create a serializer instance.

    This is a lightweight internal factory (not a plugin system).
    It centralizes format selection and keeps wiring out of the pipeline.
    """
    name = (fmt or "xml").lower().strip()

    if name == "xml":
        return XMLSerializer(formatting=formatting)

    raise ValueError(f"Unknown format: {fmt!r}. Currently supported: xml")