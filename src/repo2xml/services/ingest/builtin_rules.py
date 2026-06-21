# src/repo2xml/services/ingest/builtin_rules.py
"""Load built-in redaction rules from the bundled YAML file.

This keeps the default rules out of Python code, making them
easier to review and override.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Dict, Any

import yaml  # pyyaml is a mandatory dependency of the package now


@dataclass(slots=True)
class RedactRule:
    """A single redaction rule.

    Attributes:
        name: Unique identifier.
        pattern: Regular expression (Python re syntax).
        replacement: Text to substitute.
        groups: Group names for selective enabling.
        enabled: Whether the rule is active by default (True).
    """
    name: str
    pattern: str
    replacement: str
    groups: List[str] = field(default_factory=list)
    enabled: bool = True


def _load_builtin_yaml() -> Dict[str, Any]:
    """Load the builtin_rules.yaml resource file.

    The file is expected to be in the same directory as this module.
    """
    yaml_path = Path(__file__).with_name("builtin_rules.yaml")
    with open(yaml_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    if not isinstance(data, dict):
        raise RuntimeError("builtin_rules.yaml must contain a mapping")
    return data


def get_builtin_rules() -> List[RedactRule]:
    """Return the list of built-in redaction rules.

    The rules are read from the bundled YAML file.
    """
    data = _load_builtin_yaml()
    raw_rules: List[Dict[str, Any]] = data.get("rules", [])
    rules: List[RedactRule] = []
    for r in raw_rules:
        rules.append(RedactRule(
            name=r["name"],
            pattern=r["pattern"],
            replacement=r.get("replacement", "<redacted>"),
            groups=r.get("groups", []),
            enabled=r.get("enabled", True),
        ))
    return rules