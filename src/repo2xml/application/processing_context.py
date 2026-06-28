from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Optional

from repo2xml.domain.model import ClassificationResult, FileEntry, FilePayload, SkipCode, ErrorCode


@dataclass(slots=True)
class ProcessingContext:
    """
    Context for processing a single file entry.

    This object is passed through all steps in the pipeline. Steps may read
    and modify fields to reflect intermediate results, and can set should_stop
    to abort further processing.
    """
    entry: FileEntry

    classification: Optional[ClassificationResult] = None
    payload: Optional[FilePayload] = None
    token_count: Optional[int] = None

    should_stop: bool = False
    is_success: bool = False
    skip_code: Optional[SkipCode] = None
    error_code: Optional[ErrorCode] = None
    message: Optional[str] = None

    # Arbitrary metadata for extensions
    metadata: Dict[str, Any] = field(default_factory=dict)