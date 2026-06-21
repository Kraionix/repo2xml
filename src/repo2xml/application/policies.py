# src/repo2xml/application/policies.py
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


class ReasonFormatter:
    """Convert structured error/skip info into human-readable messages."""

    @staticmethod
    def format_skip(info: SkipInfo) -> str:
        code = info.code
        d = info.detail
        if code == SkipCode.binary_skip_mode:
            return "Skipped: Binary file detected (binary mode: skip)"
        if code == SkipCode.text_size_limit:
            size = d.get("size")
            limit = d.get("limit")
            return f"Skipped: File size {size} exceeds text limit {limit}"
        if code == SkipCode.base64_size_limit:
            size = d.get("size")
            limit = d.get("limit")
            return f"Skipped: File size {size} exceeds base64 limit {limit}"
        if code == SkipCode.hash_size_limit:
            size = d.get("size")
            limit = d.get("limit")
            return f"Skipped: File size {size} exceeds hash limit {limit}"
        return "Skipped"

    @staticmethod
    def format_error(info: ErrorInfo) -> str:
        code = info.code
        d = info.detail
        os_error = d.get("os_error")
        if code == ErrorCode.sniff_read_error:
            return f"Error reading file sample: {os_error}"
        if code == ErrorCode.stat_error:
            return f"Error stat file: {os_error}"
        if code == ErrorCode.text_read_error:
            return f"Error reading file: {os_error}"
        if code == ErrorCode.text_decode_error:
            enc = d.get("encoding", "unknown")
            return f"Error decoding with {enc}: {d.get('decode_error')}"
        if code == ErrorCode.binary_detected:
            return "Binary file detected during text read"
        if code == ErrorCode.binary_hash_error:
            return f"Error hashing file: {os_error}"
        if code == ErrorCode.base64_error:
            return f"Error base64-encoding file: {os_error}"
        if code == ErrorCode.processor_error:
            return f"Text processor error: {d.get('processor_error')}"
        return "Error"


@dataclass(slots=True)
class SymlinkPolicy:
    config: ExportConfig

    def apply(self, entry: FileEntry) -> Optional[FilePayload]:
        if entry.is_symlink and self.config.symlinks_files == SymlinkFilesMode.as_link:
            return LinkPayload(link_target=entry.symlink_target)
        if entry.is_symlink and self.config.symlinks_files == SymlinkFilesMode.skip:
            info = SkipInfo(code=SkipCode.unknown, detail={"reason": "symlink_files_mode=skip"})
            return SkippedPayload(code=info.code, message=ReasonFormatter.format_skip(info), detail=info.detail)
        return None


@dataclass(slots=True)
class ModePolicy:
    config: ExportConfig

    def apply(self, entry: FileEntry) -> Optional[FilePayload]:
        if self.config.mode == Mode.metadata:
            return MetadataPayload()
        return None


@dataclass(slots=True)
class BinaryPolicy:
    config: ExportConfig
    ingestor: IngestorLike

    def apply(self, entry: FileEntry) -> Optional[FilePayload]:
        if self.config.binary == BinaryMode.skip:
            info = SkipInfo(code=SkipCode.binary_skip_mode)
            return SkippedPayload(code=info.code, message=ReasonFormatter.format_skip(info), detail=info.detail)
        if self.config.binary == BinaryMode.hash:
            if self.config.max_hash_size > 0 and entry.size > self.config.max_hash_size:
                info = SkipInfo(code=SkipCode.hash_size_limit,
                                detail={"size": entry.size, "limit": self.config.max_hash_size})
                return SkippedPayload(code=info.code, message=ReasonFormatter.format_skip(info), detail=info.detail)
            try:
                h = self.ingestor.sha256_file(entry.abs_path)
            except OSError as e:
                err = ErrorInfo(code=ErrorCode.binary_hash_error, detail={"os_error": str(e)})
                return ErrorPayload(code=err.code, message=ReasonFormatter.format_error(err), detail=err.detail)
            return BinaryHashPayload(sha256_hex=h)
        if self.config.binary == BinaryMode.base64:
            if entry.size > self.config.max_base64_size:
                info = SkipInfo(code=SkipCode.base64_size_limit,
                                detail={"size": entry.size, "limit": self.config.max_base64_size})
                return SkippedPayload(code=info.code, message=ReasonFormatter.format_skip(info), detail=info.detail)
            try:
                chunks = self.ingestor.iter_base64_chunks(entry.abs_path)
            except OSError as e:
                err = ErrorInfo(code=ErrorCode.base64_error, detail={"os_error": str(e)})
                return ErrorPayload(code=err.code, message=ReasonFormatter.format_error(err), detail=err.detail)
            return BinaryBase64Payload(chunks=chunks)
        info = SkipInfo(code=SkipCode.unknown, detail={"binary_mode": str(self.config.binary)})
        return SkippedPayload(code=info.code, message=ReasonFormatter.format_skip(info), detail=info.detail)


@dataclass(slots=True)
class TextPolicy:
    config: ExportConfig
    ingestor: IngestorLike

    def apply(self, entry: FileEntry, *, encoding_hint: Optional[str]) -> FilePayload:
        if entry.size > self.config.max_text_size:
            info = SkipInfo(code=SkipCode.text_size_limit,
                            detail={"size": entry.size, "limit": self.config.max_text_size})
            return SkippedPayload(code=info.code, message=ReasonFormatter.format_skip(info), detail=info.detail)
        res = self.ingestor.read_text(entry.abs_path, max_size=self.config.max_text_size)
        if res.kind == "error":
            err = res.error or ErrorInfo(code=ErrorCode.unknown)
            return ErrorPayload(code=err.code, message=ReasonFormatter.format_error(err), detail=err.detail)
        if res.kind == "skip":
            info = res.skipped or SkipInfo(code=SkipCode.unknown)
            return SkippedPayload(code=info.code, message=ReasonFormatter.format_skip(info), detail=info.detail)
        text = res.text or ""
        # Text processors are no longer applied here; redaction is handled later in the pipeline.
        return TextPayload(text=text, encoding=res.encoding or encoding_hint)


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