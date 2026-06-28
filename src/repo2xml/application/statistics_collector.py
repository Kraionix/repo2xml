# src/repo2xml/application/statistics_collector.py
from __future__ import annotations

from typing import Dict, List, Optional, Any

from repo2xml.contracts import StatsProvider
from repo2xml.domain.model import ExportStats, TokenStats
from repo2xml.services.scan.scanner import ScanStats


class StatisticsCollector:
    """
    Aggregates statistics during the export process.

    Maintains counters for processed, skipped, and errored files,
    as well as token‑related statistics. It also collects statistics
    from any registered StatsProvider components.
    """

    def __init__(
        self,
        *,
        token_counting_enabled: bool = False,
        providers: Optional[List[StatsProvider]] = None,
    ):
        # Counters
        self._total_processed = 0
        self._total_skipped = 0
        self._total_errors = 0
        self._skipped_by_code: Dict[str, int] = {}
        self._errors_by_code: Dict[str, int] = {}

        # Token statistics (optional)
        self._token_stats: Optional[TokenStats] = TokenStats() if token_counting_enabled else None
        self._token_counting_enabled = token_counting_enabled

        # Stats providers – will be queried when building final stats
        self._providers: List[StatsProvider] = providers or []

    def record_success(self, token_count: Optional[int] = None, ext: str = "") -> None:
        """Record a successfully processed file."""
        self._total_processed += 1
        if self._token_counting_enabled and token_count is not None and self._token_stats is not None:
            self._token_stats.files_processed += 1
            self._token_stats.total_tokens += token_count
            if ext:
                self._token_stats.tokens_by_extension[ext] = (
                    self._token_stats.tokens_by_extension.get(ext, 0) + token_count
                )
            if token_count > self._token_stats.max_tokens:
                self._token_stats.max_tokens = token_count
            if self._token_stats.min_tokens == 0 or token_count < self._token_stats.min_tokens:
                self._token_stats.min_tokens = token_count

    def record_skipped(self, skip_code: str, message: Optional[str] = None) -> None:
        self._total_skipped += 1
        self._skipped_by_code[skip_code] = self._skipped_by_code.get(skip_code, 0) + 1

    def record_error(self, error_code: str, message: Optional[str] = None) -> None:
        self._total_errors += 1
        self._errors_by_code[error_code] = self._errors_by_code.get(error_code, 0) + 1

    def get_export_stats(self, scan_warning_summary: Optional[str] = None) -> ExportStats:
        """Return the final ExportStats object, including stats from all providers."""
        # Gather stats from providers
        redaction_stats = None
        classification_stats = None
        scan_stats = None

        for provider in self._providers:
            stats = provider.get_stats()
            # Heuristic: inspect keys to assign to known fields
            if "total_files_processed" in stats or "matches_by_rule" in stats:
                redaction_stats = stats
            elif "total_files" in stats and "by_extension" in stats:
                classification_stats = stats
            elif "dirs_scandir_errors" in stats or "errors_by_type" in stats:
                # Convert dict to a ScanStats object if needed, or keep as dict
                scan_stats = stats

        # If scan_stats is a dict, we might want to convert it to ScanStats,
        # but ExportStats accepts Any, so we can keep it as dict.
        return ExportStats(
            files_total=self._total_processed + self._total_skipped + self._total_errors,
            files_emitted=self._total_processed,
            files_skipped=self._total_skipped,
            files_errors=self._total_errors,
            skipped_by_code=dict(self._skipped_by_code),
            errors_by_code=dict(self._errors_by_code),
            scan_warning_summary=scan_warning_summary,
            redaction_stats=redaction_stats,
            classification_stats=classification_stats,
            token_stats=self._token_stats,
            scan_stats=scan_stats,
        )

    def reset(self) -> None:
        self._total_processed = 0
        self._total_skipped = 0
        self._total_errors = 0
        self._skipped_by_code.clear()
        self._errors_by_code.clear()
        if self._token_counting_enabled:
            self._token_stats = TokenStats()
        else:
            self._token_stats = None