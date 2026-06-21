# src/repo2xml/services/ingest/classify/rule_loader.py
"""Load and merge built-in and user-supplied classification configuration."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, FrozenSet, Optional

import yaml


def load_config(
    builtin_yaml_path: Path,
    user_yaml_path: Optional[Path] = None,
) -> dict:
    """
    Load the effective classification configuration.

    1. Parse the bundled *builtin_yaml_path*.
    2. If *user_yaml_path* is provided, load it and merge with built-in values.
       User lists override built-in ones (replace, not append).
    """
    with open(builtin_yaml_path, "r", encoding="utf-8") as f:
        builtin = yaml.safe_load(f)

    user = {}
    if user_yaml_path is not None:
        with open(user_yaml_path, "r", encoding="utf-8") as f:
            user = yaml.safe_load(f) or {}

    # Merge simple keys: user values take precedence
    merged = {}
    merged["text_extensions"] = _merge_list(
        builtin.get("text_extensions", []),
        user.get("text_extensions", []),
    )
    merged["binary_extensions"] = _merge_list(
        builtin.get("binary_extensions", []),
        user.get("binary_extensions", []),
    )
    merged["compound_binary_suffixes"] = _merge_list(
        builtin.get("compound_binary_suffixes", []),
        user.get("compound_binary_suffixes", []),
    )
    merged["binary_threshold"] = user.get("binary_threshold", builtin.get("binary_threshold", 0.30))
    return merged


def _merge_list(builtin: list, user: list) -> list:
    """If user provides a list, use it; otherwise keep built-in."""
    return user if user else builtin