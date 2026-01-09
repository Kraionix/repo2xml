from __future__ import annotations

import re


# This is a pragmatic, best-effort redaction helper for LLM context exports.
# It is not a full secret scanner and may produce false positives/negatives.

_RE_PRIVATE_KEY_BLOCK = re.compile(
    r"-----BEGIN(?: [A-Z0-9]+)? PRIVATE KEY-----[\s\S]*?-----END(?: [A-Z0-9]+)? PRIVATE KEY-----",
    re.MULTILINE,
)

_RE_AWS_ACCESS_KEY_ID = re.compile(r"\bAKIA[0-9A-Z]{16}\b")
_RE_GITHUB_TOKEN = re.compile(r"\bghp_[A-Za-z0-9]{30,}\b")
_RE_GENERIC_TOKEN = re.compile(r"(?i)\b(token|api[_-]?key|secret)\b\s*[:=]\s*([A-Za-z0-9_\-]{16,})")


def redact_secrets(text: str) -> str:
    """
    Redact common secret-like patterns in text.

    This is intended to reduce accidental leakage when exporting repositories
    into LLM contexts.
    """
    if not text:
        return text

    out = text

    # Private key blocks (strong signal).
    out = _RE_PRIVATE_KEY_BLOCK.sub("<redacted:private-key>", out)

    # High-confidence tokens.
    out = _RE_AWS_ACCESS_KEY_ID.sub("<redacted:aws-access-key-id>", out)
    out = _RE_GITHUB_TOKEN.sub("<redacted:github-token>", out)

    # Generic "token/api_key/secret = VALUE" patterns.
    def _sub_generic(m: re.Match) -> str:
        key = m.group(1)
        return f"{key}=<redacted:token>"

    out = _RE_GENERIC_TOKEN.sub(_sub_generic, out)

    return out