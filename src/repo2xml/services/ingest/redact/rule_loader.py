# src/repo2xml/services/ingest/redact/rule_loader.py
"""Load and merge built‑in and user‑supplied redaction rules."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

from repo2xml.services.ingest.redact.models import Rule


def load_builtin_rules() -> List[Rule]:
    """Load the default rules from the bundled YAML resource."""
    yaml_path = Path(__file__).parent / "builtin_rules.yaml"
    with open(yaml_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return [_dict_to_rule(r) for r in data.get("rules", [])]


def load_rules(
    builtin_yaml_path: Path,
    user_config: Optional[Dict[str, Any]],
) -> List[Rule]:
    """
    Build the effective list of active redaction rules.

    1. Load built‑in rules from *builtin_yaml_path*.
    2. Apply the *user_config* (if any) to filter/override rules.
    """
    # Load built‑in rules from the bundled YAML
    with open(builtin_yaml_path, "r", encoding="utf-8") as f:
        builtin_data = yaml.safe_load(f)
    builtin_rules: List[Rule] = [_dict_to_rule(r) for r in builtin_data.get("rules", [])]

    if user_config is None:
        return [r for r in builtin_rules if r.enabled]

    # --- Select built‑in rules based on 'builtin_rules' setting ---
    setting = user_config.get("builtin_rules", "all")
    if setting == "all":
        allowed_groups: set = set()
    elif setting == "none":
        builtin_rules.clear()
        allowed_groups = set()
    elif isinstance(setting, list):
        allowed_groups = set(setting)
    else:
        raise ValueError(f"Invalid builtin_rules value: {setting!r}")

    # Filter built‑in rules
    filtered_builtin: list[Rule] = []
    for rule in builtin_rules:
        if not rule.enabled:
            continue
        if allowed_groups and not allowed_groups.intersection(rule.groups):
            continue
        filtered_builtin.append(rule)

    # --- Apply user rules (add / override) ---
    user_rules = user_config.get("rules", [])
    # Build a name→rule dict for easier override
    final_rules: dict[str, Rule] = {r.name: r for r in filtered_builtin}

    for user_rule in user_rules:
        name = user_rule.get("name")
        if not name:
            raise ValueError("A user redaction rule is missing a 'name'")
        enabled = user_rule.get("enabled", True)
        # Remove any existing rule with the same name
        final_rules.pop(name, None)
        if enabled:
            pattern = user_rule.get("pattern")
            replacement = user_rule.get("replacement")
            if not pattern or replacement is None:
                raise ValueError(f"Rule '{name}' must have 'pattern' and 'replacement'")
            final_rules[name] = _dict_to_rule(user_rule)

    return list(final_rules.values())


def _dict_to_rule(d: Dict[str, Any]) -> Rule:
    return Rule(
        name=d["name"],
        pattern=d["pattern"],
        replacement=d.get("replacement", "<redacted>"),
        groups=d.get("groups", []),
        enabled=d.get("enabled", True),
    )