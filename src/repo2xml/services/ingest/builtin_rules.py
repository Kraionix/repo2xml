# src/repo2xml/services/ingest/builtin_rules.py
"""Built-in redaction rules for common secret patterns.

These rules are used by RedactionEngine when no external configuration
is provided.  They are grouped for selective enabling/disabling.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List


@dataclass(slots=True)
class RedactRule:
    """A single redaction rule.

    Attributes:
        name: Unique identifier (used for overriding via config).
        pattern: Regular expression to search for (Python re syntax).
        replacement: String to replace matches with.
        groups: List of group names this rule belongs to (e.g. "api_keys").
        enabled: Whether this rule is active by default.
    """
    name: str
    pattern: str
    replacement: str
    groups: List[str] = field(default_factory=list)
    enabled: bool = True


def get_builtin_rules() -> List[RedactRule]:
    """Return the list of built-in redaction rules.

    Each rule targets a common secret format.  They are grouped
    so that users can enable/disable whole categories.
    """
    return [
        # ---- Private keys ----
        RedactRule(
            name="private-key-block",
            pattern=r"-----BEGIN(?: [A-Z0-9]+)? PRIVATE KEY-----[\s\S]*?-----END(?: [A-Z0-9]+)? PRIVATE KEY-----",
            replacement="<redacted:private-key>",
            groups=["private_keys"],
        ),

        # ---- API keys / tokens ----
        RedactRule(
            name="aws-access-key-id",
            pattern=r"\bAKIA[0-9A-Z]{16}\b",
            replacement="<redacted:aws-access-key-id>",
            groups=["api_keys"],
        ),
        RedactRule(
            name="github-token",
            pattern=r"\bgh[opurs]_[A-Za-z0-9]{30,}\b",
            replacement="<redacted:github-token>",
            groups=["tokens"],
        ),
        RedactRule(
            name="slack-token",
            pattern=r"\bxox[abpra]-[A-Za-z0-9-]+\b",
            replacement="<redacted:slack-token>",
            groups=["tokens"],
        ),
        RedactRule(
            name="stripe-secret-key",
            pattern=r"\b[rs]k_live_[A-Za-z0-9]{24,}\b",
            replacement="<redacted:stripe-secret-key>",
            groups=["api_keys"],
        ),

        # ---- JWT ----
        RedactRule(
            name="jwt",
            pattern=r"\beyJ[A-Za-z0-9_-]{20,}\.eyJ[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{20,}\b",
            replacement="<redacted:jwt>",
            groups=["tokens"],
        ),

        # ---- Generic key=value credentials ----
        RedactRule(
            name="generic-credential",
            pattern=r"(?i)\b(password|passwd|pwd|secret|token|api[_-]?key)\b\s*[:=]\s*\S+",
            replacement=lambda m: f"{m.group(1)}=<redacted:{m.group(1)}>",
            groups=["generic"],
        ),
    ]