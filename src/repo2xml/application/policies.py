# src/repo2xml/application/policies.py
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from repo2xml.contracts import IngestorLike
from repo2xml.config import (
    BinaryHandlingConfig,
    BinaryMode,
    ExportConfig,
    Mode,
    SymlinkFilesMode,
    TextHandlingConfig,
)
from repo2xml.domain.model import (
    BinaryBase64Payload,
    BinaryHashPayload,
    ClassificationResult,
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
    symlinks_files: SymlinkFilesMode

    def apply(self, entry: FileEntry) -> Optional[FilePayload]:
        if entry.is_symlink and self.symlinks_files == SymlinkFilesMode.as_link:
            return LinkPayload(link_target=entry.symlink_target)
        if entry.is_symlink and self.symlinks_files == SymlinkFilesMode.skip:
            info = SkipInfo(code=SkipCode.unknown, detail={"reason": "symlink_files_mode=skip"})
            return SkippedPayload(code=info.code, message=ReasonFormatter.format_skip(info), detail=info.detail)
        return None


@dataclass(slots=True)
class ModePolicy:
    mode: Mode

    def apply(self, entry: FileEntry) -> Optional[FilePayload]:
        if self.mode == Mode.metadata:
            return MetadataPayload()
        return None


@dataclass(slots=True)
class BinaryPolicy:
    binary: BinaryHandlingConfig
    ingestor: IngestorLike

    def apply(self, entry: FileEntry) -> FilePayload:
        if self.binary.mode == BinaryMode.skip:
            info = SkipInfo(code=SkipCode.binary_skip_mode)
            return SkippedPayload(code=info.code, message=ReasonFormatter.format_skip(info), detail=info.detail)
        if self.binary.mode == BinaryMode.hash:
            if self.binary.max_hash_size > 0 and entry.size > self.binary.max_hash_size:
                info = SkipInfo(code=SkipCode.hash_size_limit,
                                detail={"size": entry.size, "limit": self.binary.max_hash_size})
                return SkippedPayload(code=info.code, message=ReasonFormatter.format_skip(info), detail=info.detail)
            try:
                h = self.ingestor.sha256_file(entry.abs_path)
            except OSError as e:
                err = ErrorInfo(code=ErrorCode.binary_hash_error, detail={"os_error": str(e)})
                return ErrorPayload(code=err.code, message=ReasonFormatter.format_error(err), detail=err.detail)
            return BinaryHashPayload(sha256_hex=h)
        if self.binary.mode == BinaryMode.base64:
            if entry.size > self.binary.max_base64_size:
                info = SkipInfo(code=SkipCode.base64_size_limit,
                                detail={"size": entry.size, "limit": self.binary.max_base64_size})
                return SkippedPayload(code=info.code, message=ReasonFormatter.format_skip(info), detail=info.detail)
            try:
                chunks = self.ingestor.iter_base64_chunks(entry.abs_path)
            except OSError as e:
                err = ErrorInfo(code=ErrorCode.base64_error, detail={"os_error": str(e)})
                return ErrorPayload(code=err.code, message=ReasonFormatter.format_error(err), detail=err.detail)
            return BinaryBase64Payload(chunks=chunks)
        info = SkipInfo(code=SkipCode.unknown, detail={"binary_mode": str(self.binary.mode)})
        return SkippedPayload(code=info.code, message=ReasonFormatter.format_skip(info), detail=info.detail)


@dataclass(slots=True)
class TextPolicy:
    text: TextHandlingConfig
    ingestor: IngestorLike

    def apply(self, entry: FileEntry, classification: ClassificationResult) -> FilePayload:
        if entry.size > self.text.max_text_size:
            info = SkipInfo(code=SkipCode.text_size_limit,
                            detail={"size": entry.size, "limit": self.text.max_text_size})
            return SkippedPayload(code=info.code, message=ReasonFormatter.format_skip(info), detail=info.detail)
        res = self.ingestor.read_text(
            entry.abs_path,
            max_size=self.text.max_text_size,
            sniff_sample=classification.sample,
        )
        if res.kind == "error":
            err = res.error or ErrorInfo(code=ErrorCode.unknown)
            return ErrorPayload(code=err.code, message=ReasonFormatter.format_error(err), detail=err.detail)
        if res.kind == "skip":
            info = res.skipped or SkipInfo(code=SkipCode.unknown)
            return SkippedPayload(code=info.code, message=ReasonFormatter.format_skip(info), detail=info.detail)
        text = res.text or ""
        return TextPayload(text=text, encoding=res.encoding or classification.encoding)


@dataclass(slots=True)
class ExportPayloadBuilder:
    mode: Mode
    binary: BinaryHandlingConfig
    text: TextHandlingConfig
    symlinks_files: SymlinkFilesMode
    ingestor: IngestorLike
    _symlink: SymlinkPolicy = field(init=False, repr=False)
    _mode: ModePolicy = field(init=False, repr=False)
    _binary: BinaryPolicy = field(init=False, repr=False)
    _text: TextPolicy = field(init=False, repr=False)

    def __post_init__(self) -> None:
        self._symlink = SymlinkPolicy(self.symlinks_files)
        self._mode = ModePolicy(self.mode)
        self._binary = BinaryPolicy(self.binary, self.ingestor)
        self._text = TextPolicy(self.text, self.ingestor)

    def build(self, entry: FileEntry, classification: ClassificationResult) -> FilePayload:
        p = self._symlink.apply(entry)
        if p is not None:
            return p
        p = self._mode.apply(entry)
        if p is not None:
            return p
        if classification.kind == "error":
            err = ErrorInfo(code=ErrorCode.sniff_read_error, detail={"os_error": classification.error or "unknown"})
            return ErrorPayload(code=err.code, message=ReasonFormatter.format_error(err), detail=err.detail)
        if classification.kind == "binary":
            return self._binary.apply(entry)
        return self._text.apply(entry, classification)