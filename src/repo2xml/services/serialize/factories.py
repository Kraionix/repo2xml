from __future__ import annotations

from repo2xml.domain.exceptions import SerializationError
from repo2xml.services.serialize.base import Serializer
from repo2xml.services.serialize.xml import XMLSerializer


def create_serializer(
    *,
    fmt: str,
    formatting: str,
    include_mtime: bool = True,
    include_size: bool = True,
    text_decode_errors: str = "replace",
) -> Serializer:
    """
    Create a serializer instance.

    This is a lightweight internal factory (not a plugin system).
    It centralizes format selection and keeps wiring out of the pipeline.
    """
    name = (fmt or "xml").lower().strip()

    if name == "xml":
        return XMLSerializer(
            formatting=formatting,
            include_mtime=include_mtime,
            include_size=include_size,
            text_decode_errors=text_decode_errors,
        )

    raise SerializationError(f"Unknown format: {fmt!r}. Currently supported: xml")