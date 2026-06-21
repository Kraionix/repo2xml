# src/repo2xml/services/serialize/format_spec.py
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Type

from repo2xml.domain.model import FilePayload


class FormatSpec(ABC):
    """Base class for format-specific constants and payload classification.

    Subclasses define tag/attribute names and provide a static method
    to determine the correct FilePayload variant from raw data.
    """

    @staticmethod
    @abstractmethod
    def classify_payload(raw_attrs: dict[str, str], content_info: dict[str, str] | None) -> Type[FilePayload]:
        """Given attributes and optional content metadata, return the payload type."""
        ...