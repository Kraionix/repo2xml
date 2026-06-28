# src/repo2xml/services/classify/engine.py
from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

from repo2xml.contracts import StatsProvider
from repo2xml.domain.model import FileEntry
from repo2xml.services.classify.classifiers import (
    SNIFF_BYTES,
    ExtensionClassifier,
    detect_bom,
    looks_binary,
)
from repo2xml.services.classify.models import ClassificationResult, ClassificationStats
from repo2xml.services.classify.rule_loader import load_config

logger = logging.getLogger("repo2xml.classify")


class ClassificationEngine(StatsProvider):
    """Classifies files as text or binary.

    Can be configured with an optional YAML file; otherwise built-in rules are used.
    """

    def __init__(self, root_path: Path, config_path: Optional[Path] = None):
        self._root_path = root_path
        self._stats = ClassificationStats()

        builtin_yaml = Path(__file__).parent / "builtin_rules.yaml"
        user_yaml = config_path
        if user_yaml is None:
            candidate = root_path / ".repo2xml-classify.yml"
            if candidate.is_file():
                user_yaml = candidate

        config = load_config(builtin_yaml, user_yaml)

        text_exts = frozenset(ext.lower() for ext in config["text_extensions"])
        binary_exts = frozenset(ext.lower() for ext in config["binary_extensions"])
        compound_suffixes = frozenset(s.lower() for s in config["compound_binary_suffixes"])
        self._ext_classifier = ExtensionClassifier(text_exts, binary_exts, compound_suffixes)
        self._binary_threshold = float(config["binary_threshold"])

    def classify(self, entry: FileEntry) -> ClassificationResult:
        self._stats.total_files += 1

        kind = self._ext_classifier.classify(entry.abs_path)
        if kind is not None:
            self._stats.by_extension += 1
            return ClassificationResult(kind=kind, encoding="utf-8" if kind == "text" else None)

        self._stats.by_content += 1
        try:
            with open(entry.abs_path, "rb") as f:
                sample = f.read(SNIFF_BYTES)
        except OSError as exc:
            self._stats.errors += 1
            logger.warning("Cannot read %s for classification: %s", entry.abs_path, exc)
            return ClassificationResult(kind="error", error=str(exc))

        bom_enc = detect_bom(sample)
        if looks_binary(sample, bom_enc, self._binary_threshold):
            return ClassificationResult(kind="binary", encoding=bom_enc, sample=sample)
        return ClassificationResult(kind="text", encoding=bom_enc or "utf-8", sample=sample)

    def get_stats(self) -> ClassificationStats:
        """Return classification statistics as a ClassificationStats object."""
        return self._stats