from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from repo2xml.contracts import IngestorLike
from repo2xml.services.classify import ClassificationEngine
from repo2xml.services.ingest.redact import RedactionEngine
from repo2xml.services.tokenize import TokenCounter


@dataclass(slots=True)
class ProcessingServices:
    """Container for services needed by processing steps."""

    classification_engine: ClassificationEngine
    ingestor: IngestorLike
    redaction_engine: Optional[RedactionEngine] = None
    token_counter: Optional[TokenCounter] = None