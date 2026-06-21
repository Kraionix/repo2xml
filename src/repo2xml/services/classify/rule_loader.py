# src/repo2xml/services/classify/rule_loader.py
"""Load and merge built-in and user-supplied classification configuration."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml


def load_config(
    builtin_yaml_path: Path,
    user_yaml_path: Optional[Path] = None,
) -> dict:
    """
    Load the effective classification configuration.

    1. Parse the bundled *builtin_yaml_path*.
    2. If *user_yaml_path* is provided, load it and merge with built-in values.
       - Full lists (text_extensions, binary_extensions, compound_binary_suffixes)
         replace built-in lists when present.
       - Additive keys (text_ext_add, text_ext_remove, binary_ext_add,
         binary_ext_remove, compound_binary_add, compound_binary_remove)
         modify the built-in lists when full lists are not provided.
    """
    with open(builtin_yaml_path, "r", encoding="utf-8") as f:
        builtin = yaml.safe_load(f)

    user = {}
    if user_yaml_path is not None:
        with open(user_yaml_path, "r", encoding="utf-8") as f:
            user = yaml.safe_load(f) or {}

    merged = {}

    # Text extensions
    merged["text_extensions"] = _merge_list(
        builtin.get("text_extensions", []),
        user.get("text_extensions"),
        user.get("text_ext_add"),
        user.get("text_ext_remove"),
    )

    # Binary extensions
    merged["binary_extensions"] = _merge_list(
        builtin.get("binary_extensions", []),
        user.get("binary_extensions"),
        user.get("binary_ext_add"),
        user.get("binary_ext_remove"),
    )

    # Compound binary suffixes
    merged["compound_binary_suffixes"] = _merge_list(
        builtin.get("compound_binary_suffixes", []),
        user.get("compound_binary_suffixes"),
        user.get("compound_binary_add"),
        user.get("compound_binary_remove"),
    )

    merged["binary_threshold"] = user.get("binary_threshold", builtin.get("binary_threshold", 0.30))
    return merged


def _merge_list(
    builtin: List[str],
    user_full: Optional[List[str]],
    user_add: Optional[List[str]],
    user_remove: Optional[List[str]],
) -> List[str]:
    """Merge a built-in list with user overrides.

    - If *user_full* is provided (even empty), it replaces the built-in list.
    - Otherwise, start with the built-in list, extend with *user_add*,
      and remove items present in *user_remove*.
    """
    if user_full is not None:
        # User explicitly defined the whole list – use it directly
        return user_full

    # Start with built-in
    result = list(builtin)

    # Add new items (normalise to lowercase with dot)
    if user_add:
        for ext in user_add:
            norm = _normalize_ext(ext)
            if norm and norm not in result:
                result.append(norm)

    # Remove items
    if user_remove:
        remove_set = {_normalize_ext(ext) for ext in user_remove}
        result = [ext for ext in result if ext not in remove_set]

    return result


def _normalize_ext(ext: str) -> str:
    """Normalize an extension: lowercase, ensure leading dot."""
    ext = ext.strip().lower()
    if not ext:
        return ""
    if not ext.startswith("."):
        ext = "." + ext
    return ext