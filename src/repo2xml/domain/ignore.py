# src/repo2xml/domain/ignore.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Tuple

from pathspec.patterns.gitignore.spec import GitIgnoreSpecPattern


@dataclass(slots=True, frozen=True)
class IgnoreRuleset:
    """
    A compiled ignore ruleset with a base directory scope.

    base_dir_rel:
      - POSIX path relative to repo root ("" for root)
    base_prefix:
      - base_dir_rel + "/" ("" for root), used for fast subpath derivation
    patterns:
      - compiled gitignore patterns in original file order
    """
    base_dir_rel: str
    base_prefix: str
    patterns: Tuple[GitIgnoreSpecPattern, ...]