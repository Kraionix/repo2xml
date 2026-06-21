# src/repo2xml/services/ingest/redact/engine.py
"""Pluggable redaction engine with context-aware processing and statistics."""
from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Dict, List, Optional

import yaml

from repo2xml.domain.model import FileEntry
from repo2xml.services.ingest.redact.exclusion import ExclusionManager
from repo2xml.services.ingest.redact.models import RedactionStats, Rule
from repo2xml.services.ingest.redact.rule_loader import load_rules

logger = logging.getLogger("repo2xml.redact")


class RedactionEngine:
    """Applies redaction rules to file contents.

    The engine can be created with an optional configuration file path.
    If omitted, it looks for `.repo2xml-redact.yml` in the project root.
    """

    def __init__(self, root_path: Path, config_path: Optional[Path] = None):
        """
        Args:
            root_path: The root directory of the repository being scanned.
            config_path: Optional explicit path to a YAML configuration file.
        """
        self._root_path = root_path
        self._stats = RedactionStats()

        # Resolve user configuration
        user_config = self._load_user_config(config_path)

        # Load built-in rules and merge with user config
        builtin_yaml = Path(__file__).parent / "builtin_rules.yaml"
        self._rules: List[Rule] = load_rules(builtin_yaml, user_config)

        # Compile exclusion patterns (gitignore‑style)
        exclude_patterns = user_config.get("exclude_files", []) if user_config else []
        self._exclusion = ExclusionManager(exclude_patterns)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def process(self, entry: FileEntry, text: str) -> str:
        """Apply redaction to the file content.

        Args:
            entry: Metadata of the file being processed.
            text: The decoded text content of the file.

        Returns:
            The text with secrets replaced.
        """
        if self._exclusion.is_excluded(entry.rel_path):
            self._stats.total_files_skipped += 1
            return text

        self._stats.total_files_processed += 1
        for rule in self._rules:
            if not rule.enabled:
                continue
            # re.sub supports backreferences (\1, \g<name>) natively
            new_text, count = re.subn(rule.pattern, rule.replacement, text)
            if count > 0:
                self._stats.total_matches += count
                self._stats.matches_by_rule[rule.name] = (
                    self._stats.matches_by_rule.get(rule.name, 0) + count
                )
                text = new_text
        return text

    def get_stats(self) -> RedactionStats:
        """Return accumulated statistics about the redaction process."""
        return self._stats

    # ------------------------------------------------------------------
    # Configuration loading
    # ------------------------------------------------------------------

    def _load_user_config(self, explicit_path: Optional[Path]) -> Optional[dict]:
        """Load user configuration from a file, searching the project root if needed."""
        path = explicit_path
        if path is None:
            candidate = self._root_path / ".repo2xml-redact.yml"
            if candidate.is_file():
                path = candidate

        if path is None:
            return None

        try:
            with open(path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
        except FileNotFoundError:
            raise FileNotFoundError(f"Redact config file not found: {path}")
        except yaml.YAMLError as e:
            raise ValueError(f"Invalid YAML in {path}: {e}") from e

        if not isinstance(data, dict):
            raise ValueError(f"Redact config must be a mapping, got {type(data)}")
        return data