# src/repo2xml/application/policies.py (changes: renamed builder, import from config)
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from repo2xml.application.contracts import IngestorLike
from repo2xml.config import BinaryMode, ExportConfig, Mode, SymlinkFilesMode
from repo2xml.domain.model import (
    BinaryBase64Payload,
    BinaryHashPayload,
    ErrorCode,
    ErrorInfo,
    ErrorPayload,
    FileEntry,
    FilePayload,
    LinkPayload,
    MetadataPayload,
    SkipCode,
    SkipInfo,
    SkippedPayload,
    TextPayload,
)

# ... (rest of ReasonFormatter, SymlinkPolicy, ModePolicy, BinaryPolicy, TextPolicy as before,
#      but using ExportConfig instead of Repo2XMLConfig)

class ReasonFormatter:
    @staticmethod
    def format_skip(info: SkipInfo) -> str:
        # same as before
        ...

    @staticmethod
    def format_error(info: ErrorInfo) -> str:
        # same as before
        ...


@dataclass(slots=True)
class SymlinkPolicy:
    config: ExportConfig
    # apply logic unchanged
    ...

@dataclass(slots=True)
class ModePolicy:
    config: ExportConfig
    ...

@dataclass(slots=True)
class BinaryPolicy:
    config: ExportConfig
    ingestor: IngestorLike
    ...

@dataclass(slots=True)
class TextPolicy:
    config: ExportConfig
    ingestor: IngestorLike
    ...


@dataclass(slots=True)
class ExportPayloadBuilder:
    config: ExportConfig
    ingestor: IngestorLike
    _symlink: SymlinkPolicy = field(init=False, repr=False)
    _mode: ModePolicy = field(init=False, repr=False)
    _binary: BinaryPolicy = field(init=False, repr=False)
    _text: TextPolicy = field(init=False, repr=False)

    def __post_init__(self) -> None:
        self._symlink = SymlinkPolicy(self.config)
        self._mode = ModePolicy(self.config)
        self._binary = BinaryPolicy(self.config, self.ingestor)
        self._text = TextPolicy(self.config, self.ingestor)

    def build(self, entry: FileEntry) -> FilePayload:
        p = self._symlink.apply(entry)
        if p is not None:
            return p
        p = self._mode.apply(entry)
        if p is not None:
            return p
        sniff = self.ingestor.sniff(entry.abs_path)
        if sniff.kind == "error":
            err = sniff.error or ErrorInfo(code=ErrorCode.unknown)
            return ErrorPayload(code=err.code, message=ReasonFormatter.format_error(err), detail=err.detail)
        if sniff.kind == "binary":
            return self._binary.apply(entry)
        return self._text.apply(entry, encoding_hint=sniff.encoding)


# Placeholder for future restore policies
class RestorePayloadInterpreter:
    """Decides how to handle each RestoreEntry during restore.
       Currently logic is embedded in FilesystemRestorer, but can be extracted."""
    pass