from __future__ import annotations

from typing import Optional

from repo2xml.application.processing_context import ProcessingContext
from repo2xml.application.step import Step
from repo2xml.config import BinaryHandlingConfig, BinaryMode, Mode, SymlinkFilesMode, TextHandlingConfig
from repo2xml.contracts import IngestorLike
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
    """Helper to format skip/error messages."""

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


class BuildPayloadStep(Step):
    """
    Step that builds the appropriate FilePayload for the file.

    This step encapsulates the logic that was previously spread across
    multiple policies (SymlinkPolicy, ModePolicy, ErrorPolicy, BinaryPolicy, TextPolicy).
    """

    def __init__(
        self,
        ingestor: IngestorLike,
        mode: Mode,
        binary: BinaryHandlingConfig,
        text: TextHandlingConfig,
        symlinks_files: SymlinkFilesMode,
    ) -> None:
        self._ingestor = ingestor
        self._mode = mode
        self._binary = binary
        self._text = text
        self._symlinks_files = symlinks_files

    def process(self, ctx: ProcessingContext) -> None:
        entry = ctx.entry
        classification = ctx.classification
        if classification is None:
            # Should not happen if ClassifyStep ran first
            ctx.should_stop = True
            ctx.is_success = False
            ctx.error_code = "missing_classification"
            ctx.message = "Classification result is missing"
            return

        payload = self._build_payload(entry, classification)
        ctx.payload = payload

        if isinstance(payload, (SkippedPayload, ErrorPayload)):
            ctx.should_stop = True
            ctx.is_success = False
            if isinstance(payload, SkippedPayload):
                ctx.skip_code = payload.code.value
                ctx.message = payload.message
            else:
                ctx.error_code = payload.code.value
                ctx.message = payload.message
        else:
            ctx.is_success = True

    def _build_payload(self, entry: FileEntry, classification: ClassificationResult) -> FilePayload:
        # 1. Symlink handling
        if entry.is_symlink:
            if self._symlinks_files == SymlinkFilesMode.as_link:
                return LinkPayload(link_target=entry.symlink_target)
            if self._symlinks_files == SymlinkFilesMode.skip:
                info = SkipInfo(code=SkipCode.unknown, detail={"reason": "symlink_files_mode=skip"})
                return SkippedPayload(code=info.code, message=ReasonFormatter.format_skip(info), detail=info.detail)
            # follow: continue

        # 2. Mode handling
        if self._mode == Mode.metadata:
            return MetadataPayload()

        # 3. Error handling
        if classification.kind == "error":
            err = ErrorInfo(code=ErrorCode.sniff_read_error, detail={"os_error": classification.error or "unknown"})
            return ErrorPayload(code=err.code, message=ReasonFormatter.format_error(err), detail=err.detail)

        # 4. Binary handling
        if classification.kind == "binary":
            return self._handle_binary(entry)

        # 5. Text handling
        if classification.kind == "text":
            return self._handle_text(entry, classification)

        # Fallback
        return ErrorPayload(
            code=ErrorCode.unknown,
            message="Unhandled classification kind",
            detail={"kind": classification.kind},
        )

    def _handle_binary(self, entry: FileEntry) -> FilePayload:
        if self._binary.mode == BinaryMode.skip:
            info = SkipInfo(code=SkipCode.binary_skip_mode)
            return SkippedPayload(code=info.code, message=ReasonFormatter.format_skip(info), detail=info.detail)

        if self._binary.mode == BinaryMode.hash:
            if self._binary.max_hash_size > 0 and entry.size > self._binary.max_hash_size:
                info = SkipInfo(
                    code=SkipCode.hash_size_limit,
                    detail={"size": entry.size, "limit": self._binary.max_hash_size},
                )
                return SkippedPayload(code=info.code, message=ReasonFormatter.format_skip(info), detail=info.detail)
            try:
                h = self._ingestor.sha256_file(entry.abs_path)
            except OSError as e:
                err = ErrorInfo(code=ErrorCode.binary_hash_error, detail={"os_error": str(e)})
                return ErrorPayload(code=err.code, message=ReasonFormatter.format_error(err), detail=err.detail)
            return BinaryHashPayload(sha256_hex=h)

        if self._binary.mode == BinaryMode.base64:
            if entry.size > self._binary.max_base64_size:
                info = SkipInfo(
                    code=SkipCode.base64_size_limit,
                    detail={"size": entry.size, "limit": self._binary.max_base64_size},
                )
                return SkippedPayload(code=info.code, message=ReasonFormatter.format_skip(info), detail=info.detail)
            try:
                chunks = self._ingestor.iter_base64_chunks(entry.abs_path)
            except OSError as e:
                err = ErrorInfo(code=ErrorCode.base64_error, detail={"os_error": str(e)})
                return ErrorPayload(code=err.code, message=ReasonFormatter.format_error(err), detail=err.detail)
            return BinaryBase64Payload(chunks=chunks)

        # Should not happen
        info = SkipInfo(code=SkipCode.unknown, detail={"binary_mode": str(self._binary.mode)})
        return SkippedPayload(code=info.code, message=ReasonFormatter.format_skip(info), detail=info.detail)

    def _handle_text(self, entry: FileEntry, classification: ClassificationResult) -> FilePayload:
        if entry.size > self._text.max_text_size:
            info = SkipInfo(
                code=SkipCode.text_size_limit,
                detail={"size": entry.size, "limit": self._text.max_text_size},
            )
            return SkippedPayload(code=info.code, message=ReasonFormatter.format_skip(info), detail=info.detail)

        res = self._ingestor.read_text(
            entry.abs_path,
            max_size=self._text.max_text_size,
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