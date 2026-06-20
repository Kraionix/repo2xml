# src/repo2xml/services/ingest/redact.py
from __future__ import annotations

import re


# This is a pragmatic, best-effort redaction helper for LLM context exports.
# It is not a full secret scanner and may produce false positives/negatives.

_RE_PRIVATE_KEY_BLOCK = re.compile(
    r"-----BEGIN(?: [A-Z0-9]+)? PRIVATE KEY-----[\s\S]*?-----END(?: [A-Z0-9]+)? PRIVATE KEY-----",
    re.MULTILINE,
)

# High-confidence tokens
_RE_AWS_ACCESS_KEY_ID = re.compile(r"\bAKIA[0-9A-Z]{16}\b")
_RE_GITHUB_TOKEN = re.compile(r"\bgh[opurs]_[A-Za-z0-9]{30,}\b")
_RE_SLACK_TOKEN = re.compile(r"\bxox[abpra]-[A-Za-z0-9-]+\b")
_RE_STRIPE_SECRET_KEY = re.compile(r"\b[rs]k_live_[A-Za-z0-9]{24,}\b")

# JWT: three base64url sections separated by dots, starting with eyJ
_RE_JWT = re.compile(r"\beyJ[A-Za-z0-9_-]{20,}\.eyJ[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{20,}\b")

# Credentials in key=value patterns (case-insensitive keywords)
_RE_CREDENTIAL_PATTERN = re.compile(
    r"(?i)\b(password|passwd|pwd|secret|token|api[_-]?key)\b\s*[:=]\s*\S+",
)


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
    out = _RE_SLACK_TOKEN.sub("<redacted:slack-token>", out)
    out = _RE_STRIPE_SECRET_KEY.sub("<redacted:stripe-secret-key>", out)

    # JWT tokens (header.payload.signature).
    out = _RE_JWT.sub("<redacted:jwt>", out)

    # Generic "key = value" patterns for common credential names.
    def _sub_generic(m: re.Match) -> str:
        key = m.group(1)
        return f"{key}=<redacted:{key}>"

    out = _RE_CREDENTIAL_PATTERN.sub(_sub_generic, out)

    return out