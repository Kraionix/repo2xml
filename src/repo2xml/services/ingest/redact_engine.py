# src/repo2xml/services/ingest/redact_engine.py
"""Extensible redaction engine with YAML-based configuration.

Automatically discovers .repo2xml-redact.yml in the project root
if no explicit config path is given.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Callable, Dict, List, Optional, Pattern, Union

import yaml

from repo2xml.domain.exceptions import ConfigurationError
from repo2xml.services.ingest.builtin_rules import RedactRule, get_builtin_rules

logger = logging.getLogger("repo2xml.redact")


class RedactionEngine:
    """A callable text processor that applies redaction rules.

    Implements the `TextProcessor` protocol (Callable[[str], str]).
    """

    def __init__(self, config_path: Optional[Path] = None, root_path: Optional[Path] = None):
        """
        Args:
            config_path: Path to a YAML configuration file. If None,
                the engine looks for .repo2xml-redact.yml in `root_path`
                (if provided) before falling back to built-in rules.
            root_path: The root of the repository being scanned (used
                to locate the default config file).
        Raises:
            ConfigurationError: If a config file is given but cannot
                be loaded, or contains invalid data.
        """
        self._rules: List[_CompiledRule] = []
        self._exclude_patterns: List[Pattern[str]] = []

        # Determine which config file to use
        effective_config_path = self._resolve_config_path(config_path, root_path)
        user_config = self._load_config(effective_config_path) if effective_config_path else {}

        # Load built-in rules (from bundled YAML)
        builtin = get_builtin_rules()

        # Determine which built-in groups to keep
        builtin_setting = user_config.get("builtin_rules", "all")
        if builtin_setting == "all":
            self._add_builtin_rules(builtin, set())
        elif builtin_setting == "none":
            pass  # no built-in rules
        elif isinstance(builtin_setting, list):
            allowed_groups = set(builtin_setting)
            self._add_builtin_rules(builtin, allowed_groups)
        else:
            raise ConfigurationError(
                f"Invalid builtin_rules value: {builtin_setting!r}"
            )

        # Apply user rules (additions / overrides)
        user_rules = user_config.get("rules", [])
        for rule_dict in user_rules:
            name = rule_dict.get("name")
            if not name:
                raise ConfigurationError("A redaction rule is missing a 'name'")
            pattern = rule_dict.get("pattern")
            replacement = rule_dict.get("replacement")
            enabled = rule_dict.get("enabled", True)

            # Remove any existing built-in with the same name
            self._rules = [r for r in self._rules if r.name != name]

            if enabled:
                if not pattern or replacement is None:
                    raise ConfigurationError(
                        f"Rule '{name}' must have 'pattern' and 'replacement'"
                    )
                self._add_rule(name, pattern, replacement)

        # Compile exclude file patterns (glob-style)
        exclude_globs = user_config.get("exclude_files", [])
        for glob in exclude_globs:
            try:
                import fnmatch
                regex = fnmatch.translate(glob)
                self._exclude_patterns.append(re.compile(regex))
            except Exception as e:
                logger.warning("Invalid exclude pattern %r: %s", glob, e)

    def __call__(self, text: str) -> str:
        """Apply all active redaction rules to the given text."""
        if not text:
            return text
        for compiled in self._rules:
            if compiled.replacement_is_callable:
                text = compiled.pattern.sub(compiled.replacement_callable, text)
            else:
                text = compiled.pattern.sub(compiled.replacement_str, text)
        return text

    def should_skip(self, rel_path: str) -> bool:
        """Check if a file should be skipped based on exclude patterns."""
        for pat in self._exclude_patterns:
            if pat.match(rel_path):
                return True
        return False

    @staticmethod
    def _resolve_config_path(explicit: Optional[Path], root_path: Optional[Path]) -> Optional[Path]:
        """Determine which configuration file to load.

        Priority:
        1) Explicitly provided path (--redact-config).
        2) .repo2xml-redact.yml in the root_path (if root_path is given and file exists).
        3) None (use built-in rules).
        """
        if explicit is not None:
            return explicit
        if root_path is not None:
            candidate = root_path / ".repo2xml-redact.yml"
            if candidate.is_file():
                return candidate
        return None

    @staticmethod
    def _load_config(path: Path) -> dict:
        """Load a YAML configuration file.

        Raises ConfigurationError if the file cannot be read or parsed.
        """
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
        except FileNotFoundError:
            raise ConfigurationError(f"Redact config file not found: {path}")
        except yaml.YAMLError as e:
            raise ConfigurationError(f"Invalid YAML in {path}: {e}") from e
        if not isinstance(data, dict):
            raise ConfigurationError(f"Redact config must be a mapping, got {type(data)}")
        return data

    def _add_builtin_rules(self, builtin: List[RedactRule], allowed_groups: set) -> None:
        """Add built-in rules that are in the allowed groups (or all if set is empty)."""
        for rule in builtin:
            if not rule.enabled:
                continue
            if allowed_groups and not allowed_groups.intersection(rule.groups):
                continue
            self._add_rule(rule.name, rule.pattern, rule.replacement)

    def _add_rule(self, name: str, pattern: str, replacement: Union[str, Callable]) -> None:
        """Compile a pattern and add it to the internal rule list."""
        compiled = re.compile(pattern)
        is_callable = callable(replacement)
        self._rules.append(_CompiledRule(
            name=name,
            pattern=compiled,
            replacement_str=replacement if not is_callable else "",
            replacement_callable=replacement if is_callable else None,
            replacement_is_callable=is_callable,
        ))


class _CompiledRule:
    """Internal representation of a compiled redaction rule."""
    __slots__ = (
        "name",
        "pattern",
        "replacement_str",
        "replacement_callable",
        "replacement_is_callable",
    )

    def __init__(
        self,
        name: str,
        pattern: Pattern[str],
        replacement_str: str,
        replacement_callable: Optional[Callable] = None,
        replacement_is_callable: bool = False,
    ):
        self.name = name
        self.pattern = pattern
        self.replacement_str = replacement_str
        self.replacement_callable = replacement_callable
        self.replacement_is_callable = replacement_is_callable