# src/repo2xml/services/serialize/xml/format_spec.py
from __future__ import annotations

from typing import Type

from repo2xml.domain.model import (
    BinaryBase64Payload,
    BinaryHashPayload,
    ErrorPayload,
    FilePayload,
    LinkPayload,
    MetadataPayload,
    SkippedPayload,
    TextPayload,
)
from repo2xml.services.serialize.format_spec import FormatSpec


class XmlFormatSpec(FormatSpec):
    # Tag and attribute names used in the XML format
    TAG_ROOT = "repository_context"
    TAG_META = "meta"
    TAG_ROOT_PATH = "root_path"
    TAG_GENERATED_AT = "generated_at_utc"
    TAG_PROJECT_STRUCTURE = "project_structure"
    TAG_DIR = "dir"
    TAG_FILE = "file"
    TAG_FILES = "files"
    TAG_CONTENT = "content"
    TAG_ERROR = "error"
    TAG_DETAIL = "detail"
    TAG_STATISTICS = "statistics"          # new for v1.2

    ATTR_VERSION = "version"
    ATTR_TOOL_VERSION = "tool_version"
    ATTR_PATH = "path"
    ATTR_NAME = "name"
    ATTR_EXT = "ext"
    ATTR_SIZE = "size"
    ATTR_MTIME = "mtime_utc"
    ATTR_SYMLINK = "symlink"
    ATTR_LINK_TARGET = "link_target"
    ATTR_LINK_ONLY = "link_only"
    ATTR_BINARY = "binary"
    ATTR_SKIPPED = "skipped"
    ATTR_SKIP_CODE = "skip_code"
    ATTR_ERROR_CODE = "error_code"
    ATTR_ENCODING = "encoding"
    ATTR_DECODE_ERRORS = "decode_errors"
    ATTR_MODE = "mode"
    ATTR_TOKENS = "tokens"                 # new for v1.2
    ATTR_TOTAL_TOKENS = "total_tokens"     # new for v1.2

    @staticmethod
    def classify_payload(raw_attrs: dict[str, str], content_info: dict[str, str] | None) -> Type[FilePayload]:
        if raw_attrs.get(XmlFormatSpec.ATTR_SKIPPED) == "true":
            if raw_attrs.get(XmlFormatSpec.ATTR_SKIP_CODE):
                return SkippedPayload
            return ErrorPayload
        if raw_attrs.get(XmlFormatSpec.ATTR_LINK_ONLY) == "true":
            return LinkPayload
        if raw_attrs.get(XmlFormatSpec.ATTR_BINARY) == "true":
            if content_info and content_info.get(XmlFormatSpec.ATTR_ENCODING) == "base64":
                return BinaryBase64Payload
            return BinaryHashPayload
        if content_info is not None:
            return TextPayload
        return MetadataPayload